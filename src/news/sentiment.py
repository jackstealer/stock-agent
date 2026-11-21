"""
Sentiment scoring for collected news headlines.

Design principles
-----------------
* Point-in-time safe: scores are keyed to `collected_at`, not `published_at`.
* No LLM API calls during backtests: scores are pre-computed and cached to a
  JSONL file, exactly like the raw headlines.
* One scorer per configuration: with no API key every headline gets the offline
  lexicon score. With GEMINI_API_KEY set (headlines are then sent to Google), a
  failed call leaves the headline unscored so the next run retries it; it is never
  silently given a lexicon score, which would mix two measures in one feature.
  Every record stores which scorer produced it.
* Deterministic at inference time: given the same headline text the same score
  is returned every time (models are not retrained on the fly).

Score convention
----------------
  +1.0 = clearly positive (profit beat, upgrade, strong guidance)
   0.0 = neutral / no information
  -1.0 = clearly negative (loss, downgrade, regulatory action)

All intermediate values are valid. The field is called `sentiment` throughout.

Usage
-----
    # Score un-scored headlines of last month and this month (UTC), as the
    # nightly chain does; or name months explicitly:
    python -m src.news.sentiment
    python -m src.news.sentiment --month 2026-11

    # Query a date range:
    from src.news.sentiment import load_scores
    df = load_scores("RELIANCE.NS", "2026-10-01", "2026-10-31")
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Lexicon-based fallback scorer (no API needed)
# ---------------------------------------------------------------------------

_POSITIVE_WORDS = {
    "profit", "beat", "beats", "record", "upgrade", "surge", "growth",
    "strong", "boost", "expansion", "dividend", "acquisition", "partnership",
    "wins", "outperform", "raised", "rally", "bullish", "revenue", "gain",
    "award", "launch", "approved", "positive", "recovery", "increase",
    "delivers", "milestone", "agreement", "deal", "orders",
}

_NEGATIVE_WORDS = {
    "loss", "losses", "decline", "drops", "falls", "crash", "downgrade",
    "miss", "misses", "weak", "cut", "cuts", "layoffs", "fraud", "penalty",
    "fine", "lawsuit", "probe", "delay", "warning", "concern", "negative",
    "bearish", "selloff", "slump", "disappoints", "shortfall", "default",
    "halt", "ban", "recall", "risk", "debt",
}


def _lexicon_score(title: str) -> float:
    """Very simple bag-of-words score in [-1, 1]. Used as fallback."""
    words = re.findall(r"[a-z]+", title.lower())
    pos = sum(1 for w in words if w in _POSITIVE_WORDS)
    neg = sum(1 for w in words if w in _NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


# ---------------------------------------------------------------------------
# LLM-based scorer (Google Gemini via REST, optional)
# ---------------------------------------------------------------------------

_PROMPT_TMPL = (
    "You are a financial sentiment classifier. "
    "Rate the sentiment of the following news headline about an Indian stock "
    "on a scale from -1.0 (very negative) to +1.0 (very positive), "
    "where 0.0 is neutral. "
    "Reply with ONLY a decimal number, nothing else.\n\n"
    "Headline: {title}"
)


def _gemini_score(title: str, api_key: str, model: str = "gemini-2.0-flash",
                  retries: int = 3) -> float | None:
    """Call the Gemini API and parse the returned float. Returns None on failure."""
    import requests  # already in requirements.txt

    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={api_key}")
    body = {"contents": [{"parts": [{"text": _PROMPT_TMPL.format(title=title)}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 10}}

    for attempt in range(retries):
        try:
            r = requests.post(url, json=body, timeout=15)
            r.raise_for_status()
            text = (r.json()["candidates"][0]["content"]["parts"][0]["text"]
                    .strip().replace(",", "."))
            val = float(text)
            return max(-1.0, min(1.0, val))
        except (KeyError, ValueError, requests.RequestException):
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return None


# ---------------------------------------------------------------------------
# Core: score a batch of headline records
# ---------------------------------------------------------------------------

def score_record(rec: dict, api_key: str | None) -> dict | None:
    """Return the record enriched with `sentiment` and `scorer` fields, or None
    if the API scorer is configured but failed (the caller retries later)."""
    title = rec.get("title", "")
    if api_key:
        val = _gemini_score(title, api_key)
        if val is None:
            return None
        return {**rec, "sentiment": round(val, 4), "scorer": "gemini"}
    return {**rec, "sentiment": round(_lexicon_score(title), 4), "scorer": "lexicon"}


# ---------------------------------------------------------------------------
# Storage: one JSONL file per month, parallel to data/news/
# ---------------------------------------------------------------------------

def _scores_path(root: str, month: str) -> Path:
    """month is 'YYYY-MM', e.g. '2026-11'."""
    return Path(root) / f"{month}.jsonl"


def _load_scored_ids(path: Path) -> set:
    if not path.exists():
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                ids.add(json.loads(line)["id"])
            except (KeyError, json.JSONDecodeError):
                pass
    return ids


def score_month(month: str, news_root: str = "data/news",
                scores_root: str = "data/sentiment",
                api_key: str | None = None) -> tuple[int, int]:
    """Score all un-scored headlines for one month. Returns (written, failed)."""
    news_file = Path(news_root) / f"{month}.jsonl"
    if not news_file.exists():
        return 0, 0

    scores_file = _scores_path(scores_root, month)
    scored_ids = _load_scored_ids(scores_file)

    records = []
    for line in news_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    new_records = [r for r in records if r.get("id") not in scored_ids]
    if not new_records:
        return 0, 0

    scores_file.parent.mkdir(parents=True, exist_ok=True)
    written = failed = 0
    with open(scores_file, "a", encoding="utf-8") as fh:
        for rec in new_records:
            scored = score_record(rec, api_key)
            if scored is None:
                failed += 1
                continue
            fh.write(json.dumps(scored, ensure_ascii=False) + "\n")
            written += 1
            # be polite if using the API
            if api_key and written % 10 == 0:
                time.sleep(1)

    return written, failed


# ---------------------------------------------------------------------------
# Query: load scored headlines for a ticker and date range
# ---------------------------------------------------------------------------

def load_scores(ticker: str, start: str, end: str,
                scores_root: str = "data/sentiment") -> pd.DataFrame:
    """Return a DataFrame with columns: collected_at, title, sentiment, scorer.

    `start` and `end` are 'YYYY-MM-DD' strings (inclusive). Keyed to
    `collected_at` (UTC) so the data is point-in-time safe.
    """
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)

    # collect all relevant month files
    months = pd.date_range(start[:7], end[:7], freq="MS").strftime("%Y-%m").tolist()
    rows = []
    for month in months:
        p = _scores_path(scores_root, month)
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("ticker") != ticker:
                continue
            try:
                ts = pd.Timestamp(rec["collected_at"]).tz_convert("UTC")
            except Exception:
                continue
            if start_ts <= ts < end_ts:
                rows.append({"collected_at": ts, "title": rec.get("title", ""),
                             "sentiment": rec.get("sentiment", 0.0),
                             "scorer": rec.get("scorer", "unknown")})

    if not rows:
        return pd.DataFrame(columns=["collected_at", "title", "sentiment", "scorer"])
    df = pd.DataFrame(rows).sort_values("collected_at").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Daily sentiment feature: rolling mean sentiment per ticker
# ---------------------------------------------------------------------------

def sentiment_feature(ticker: str, dates: pd.DatetimeIndex,
                      lookback_days: int = 3,
                      scores_root: str = "data/sentiment") -> pd.Series:
    """Return a Series indexed by `dates` (IST timezone-aware) with the mean
    sentiment score from the past `lookback_days` calendar days of headlines.

    Values are NaN on days with no collected headlines in the lookback window.
    This is the feature that Experiment 4 will consume.
    """
    if dates.empty:
        return pd.Series(dtype=float, name="sentiment")

    start = (dates.min() - pd.Timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end = dates.max().strftime("%Y-%m-%d")

    scored = load_scores(ticker, start, end, scores_root)
    if scored.empty:
        return pd.Series(float("nan"), index=dates, name="sentiment")

    scored = scored.set_index("collected_at")["sentiment"]
    scored.index = scored.index.tz_convert("Asia/Kolkata").normalize()

    result = []
    for day in dates:
        window_start = day - pd.Timedelta(days=lookback_days)
        mask = (scored.index >= window_start) & (scored.index < day)
        vals = scored[mask]
        result.append(vals.mean() if not vals.empty else float("nan"))

    return pd.Series(result, index=dates, name="sentiment")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def default_months(now: pd.Timestamp | None = None) -> list[str]:
    """Last month and this month in UTC: news files are keyed by the UTC month of
    collected_at, and including last month catches a run missed at month end."""
    now = now if now is not None else pd.Timestamp.now(tz="UTC")
    last_month = now.replace(day=1) - pd.Timedelta(days=1)
    return [last_month.strftime("%Y-%m"), now.strftime("%Y-%m")]


def main(argv=None) -> int:
    """Exit 0 when everything was scored, 1 when API calls failed (retried next run),
    2 on a malformed month, so the nightly chain log shows any problem."""
    argv = sys.argv[1:] if argv is None else argv
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY") or None

    months = [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "--month"]
    if not months and argv:
        print("usage: python -m src.news.sentiment [--month YYYY-MM ...]")
        return 2
    months = months or default_months()
    bad = [m for m in months if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", m)]
    if bad:
        print(f"invalid month(s) {bad}: expected YYYY-MM")
        return 2

    scorer = "gemini" if api_key else "lexicon"
    total = failed = 0
    for month in months:
        n, f = score_month(month, api_key=api_key)
        print(f"{month}: {n} new scores written ({scorer}), {f} failed")
        total, failed = total + n, failed + f
    print(f"Total: {total} new scores, {failed} failed (retried next run)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

