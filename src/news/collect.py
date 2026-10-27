import hashlib
import json
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
import yaml

from ..monitor.alerts import send_alert

FEED = "https://news.google.com/rss/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (stock-agent personal research collector)"}
LOOKBACK = "2d"        # overlap between daily runs; duplicates are dropped
IST = timezone(timedelta(hours=5, minutes=30))


def make_id(ticker: str, title: str, source: str) -> str:
    return hashlib.sha1(f"{ticker}|{title}|{source}".encode("utf-8")).hexdigest()[:16]


def fetch_feed(query: str) -> str:
    r = requests.get(FEED, headers=HEADERS, timeout=20, params={
        "q": f'"{query}" when:{LOOKBACK}', "hl": "en-IN", "gl": "IN",
        "ceid": "IN:en"})
    r.raise_for_status()
    return r.text


def parse_feed(xml_text: str, ticker: str, collected_at: str) -> list:
    """collected_at is when WE saw the item. It is the only trustworthy time for
    point-in-time backtests; published_at is the source's claim."""
    items = []
    for it in ET.fromstring(xml_text).iter("item"):
        title = (it.findtext("title") or "").strip()
        if not title:
            continue
        src = it.find("source")
        source = (src.text or "").strip() if src is not None else ""
        pub = it.findtext("pubDate")
        try:
            published = (parsedate_to_datetime(pub).astimezone(timezone.utc)
                         .isoformat()) if pub else None
        except (TypeError, ValueError):
            published = None
        items.append({"id": make_id(ticker, title, source), "ticker": ticker,
                      "title": title, "source": source,
                      "link": (it.findtext("link") or "").strip(),
                      "published_at": published, "collected_at": collected_at})
    return items


def _existing_ids(path: Path) -> set:
    ids = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            ids = {json.loads(line)["id"] for line in f if line.strip()}
    return ids


def append_items(items: list, root="data/news") -> int:
    """Append-only, one file per month. Dedupes within the month's file; a headline
    that straddles a month boundary can appear twice, so analysis should keep the
    earliest collected_at per id."""
    if not items:
        return 0
    path = Path(root) / f"{items[0]['collected_at'][:7]}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    seen, new = _existing_ids(path), []
    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"])
            new.append(it)
    with open(path, "a", encoding="utf-8") as f:
        for it in new:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    return len(new)


def run(config_path="configs/config.yaml", root="data/news",
        fetch=fetch_feed, alert=send_alert) -> int:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    names, tickers = cfg.get("news_names", {}), cfg["tickers"]
    missing = [t for t in tickers if t not in names]
    if missing:
        raise ValueError(f"news_names missing for: {missing}")

    collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fetched = added = 0
    failed = []
    for t in tickers:
        try:
            items = parse_feed(fetch(names[t]), t, collected_at)
            fetched += len(items)
            added += append_items(items, root)
        except Exception as e:
            failed.append(f"{t}: {e}")
        time.sleep(1)          # be polite to the feed

    print(f"news: {added} new headlines ({fetched} fetched) across {len(tickers)} stocks")
    problems = []
    if failed:
        problems.append(f"{len(failed)} feed(s) failed: " + "; ".join(failed[:5]))
    if fetched == 0 and datetime.now(IST).weekday() < 5:
        problems.append("zero headlines fetched for every stock: the feed may be broken")
    if problems:
        alert("news collector:\n" + "\n".join(problems))
        return 1
    return 0


def main() -> None:
    try:
        code = run()
    except Exception:
        send_alert("news collector CRASHED:\n" + traceback.format_exc()[-1500:])
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()