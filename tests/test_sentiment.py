"""Tests for src/news/sentiment.py: all offline, no API calls."""

import json

import pandas as pd
import pytest

from src.news.sentiment import (
    _lexicon_score,
    default_months,
    load_scores,
    score_month,
    score_record,
    sentiment_feature,
)


# ---------------------------------------------------------------------------
# Lexicon scorer
# ---------------------------------------------------------------------------

def test_lexicon_positive():
    assert _lexicon_score("Reliance beats profit record") > 0


def test_lexicon_negative():
    assert _lexicon_score("TCS issues warning, layoffs coming") < 0


def test_lexicon_neutral():
    assert _lexicon_score("Company to hold AGM next week") == 0.0


def test_lexicon_mixed():
    score = _lexicon_score("Infosys beats revenue but warns of loss")
    assert -1.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# score_record: always returns a sentinel field
# ---------------------------------------------------------------------------

def make_rec(title, ticker="RELIANCE.NS"):
    return {
        "id": "abc123",
        "ticker": ticker,
        "title": title,
        "source": "Mint",
        "link": "http://example.com",
        "published_at": "2026-11-01T08:00:00+00:00",
        "collected_at": "2026-11-01T08:00:00+00:00",
    }


def test_score_record_without_api_uses_lexicon():
    rec = make_rec("Reliance profit beats estimates")
    out = score_record(rec, api_key=None)
    assert "sentiment" in out and "scorer" in out
    assert out["scorer"] == "lexicon"
    assert -1.0 <= out["sentiment"] <= 1.0
    assert out["id"] == "abc123"          # original fields preserved


def test_score_record_preserves_all_fields():
    rec = make_rec("Neutral headline")
    out = score_record(rec, api_key=None)
    assert out["ticker"] == "RELIANCE.NS"
    assert out["source"] == "Mint"


# ---------------------------------------------------------------------------
# score_month: reads news JSONL, writes scored JSONL
# ---------------------------------------------------------------------------

def _write_news(tmp_path, month, records):
    f = tmp_path / "news" / f"{month}.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")


def test_score_month_creates_scored_file(tmp_path):
    records = [make_rec("Reliance profit up"), make_rec("ITC launches plant", "ITC.NS")]
    _write_news(tmp_path, "2026-11", records)

    n, failed = score_month("2026-11", news_root=str(tmp_path / "news"),
                            scores_root=str(tmp_path / "scores"), api_key=None)
    assert (n, failed) == (2, 0)
    score_file = tmp_path / "scores" / "2026-11.jsonl"
    assert score_file.exists()
    lines = [json.loads(l) for l in score_file.read_text().splitlines() if l.strip()]
    assert len(lines) == 2
    assert all("sentiment" in l for l in lines)


def test_score_month_is_idempotent(tmp_path):
    records = [make_rec("Reliance profit up")]
    _write_news(tmp_path, "2026-11", records)

    n1, _ = score_month("2026-11", news_root=str(tmp_path / "news"),
                        scores_root=str(tmp_path / "scores"), api_key=None)
    n2, _ = score_month("2026-11", news_root=str(tmp_path / "news"),
                        scores_root=str(tmp_path / "scores"), api_key=None)
    assert n1 == 1
    assert n2 == 0                         # already scored, skip


def test_score_month_missing_news_file_returns_zero(tmp_path):
    assert score_month("2099-01", news_root=str(tmp_path / "news"),
                       scores_root=str(tmp_path / "scores"), api_key=None) == (0, 0)


def test_failed_api_call_is_not_replaced_by_lexicon_and_is_retried(tmp_path, monkeypatch):
    import src.news.sentiment as s
    _write_news(tmp_path, "2026-11", [make_rec("Reliance profit up")])
    roots = dict(news_root=str(tmp_path / "news"), scores_root=str(tmp_path / "scores"))

    monkeypatch.setattr(s, "_gemini_score", lambda title, key: None)    # API down
    assert score_month("2026-11", api_key="k", **roots) == (0, 1)

    monkeypatch.setattr(s, "_gemini_score", lambda title, key: 0.5)     # API back
    assert score_month("2026-11", api_key="k", **roots) == (1, 0)
    rows = [json.loads(l) for l in (tmp_path / "scores" / "2026-11.jsonl").read_text().splitlines()]
    assert [r["scorer"] for r in rows] == ["gemini"]


@pytest.mark.parametrize("day, months", [("2026-11-21", ["2026-10", "2026-11"]),
                                         ("2026-01-01", ["2025-12", "2026-01"])])
def test_default_months_are_last_and_this_month_utc(day, months):
    assert default_months(pd.Timestamp(day, tz="UTC")) == months


@pytest.fixture
def cli(tmp_path, monkeypatch):
    """Run main() in an empty folder with no API key, whatever the real .env holds."""
    import src.news.sentiment as s
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s, "load_dotenv", lambda: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return s.main


def test_cli_rejects_a_malformed_month(cli):
    # the old nightly chain passed "-1-" from a locale-dependent %date% slice
    assert cli(["--month", "-1-"]) == 2
    assert cli(["--bogus"]) == 2


def test_cli_without_arguments_scores_default_months(cli):
    assert cli([]) == 0


# ---------------------------------------------------------------------------
# load_scores: query scored headlines for a ticker and date range
# ---------------------------------------------------------------------------

def _write_scored(tmp_path, month, records):
    f = tmp_path / "scores" / f"{month}.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")


def make_scored(title, ticker, day, sentiment):
    return {
        "id": f"{ticker}-{day}",
        "ticker": ticker,
        "title": title,
        "source": "test",
        "link": "",
        "published_at": None,
        "collected_at": f"{day}T06:00:00+00:00",
        "sentiment": sentiment,
        "scorer": "lexicon",
    }


def test_load_scores_filters_by_ticker_and_date(tmp_path):
    records = [
        make_scored("Reliance profit", "RELIANCE.NS", "2026-10-27", 0.8),
        make_scored("Reliance warning", "RELIANCE.NS", "2026-10-28", -0.5),
        make_scored("TCS upgrade", "TCS.NS", "2026-10-27", 0.9),
    ]
    _write_scored(tmp_path, "2026-10", records)

    df = load_scores("RELIANCE.NS", "2026-10-27", "2026-10-28",
                     scores_root=str(tmp_path / "scores"))
    assert len(df) == 2
    assert set(df["ticker"]) == {"RELIANCE.NS"} if "ticker" in df.columns \
        else True          # ticker col may not be present; sentiment must be


def test_load_scores_empty_when_no_data(tmp_path):
    df = load_scores("RELIANCE.NS", "2099-01-01", "2099-01-31",
                     scores_root=str(tmp_path / "scores"))
    assert df.empty


def test_load_scores_spans_month_boundary(tmp_path):
    oct_rec = make_scored("Oct headline", "RELIANCE.NS", "2026-10-31", 0.5)
    nov_rec = make_scored("Nov headline", "RELIANCE.NS", "2026-11-01", 0.3)
    _write_scored(tmp_path, "2026-10", [oct_rec])
    _write_scored(tmp_path, "2026-11", [nov_rec])

    df = load_scores("RELIANCE.NS", "2026-10-30", "2026-11-02",
                     scores_root=str(tmp_path / "scores"))
    assert len(df) == 2


# ---------------------------------------------------------------------------
# sentiment_feature: rolling mean, indexed by trading-day DatetimeIndex
# ---------------------------------------------------------------------------

def _setup_sentiment(tmp_path, ticker, day_scores):
    """day_scores: list of (date_str, sentiment) tuples."""
    records_by_month = {}
    for date_str, sent in day_scores:
        month = date_str[:7]
        records_by_month.setdefault(month, []).append(
            make_scored(f"headline {date_str}", ticker, date_str, sent))
    for month, recs in records_by_month.items():
        _write_scored(tmp_path, month, recs)


def test_sentiment_feature_rolling_mean(tmp_path):
    _setup_sentiment(tmp_path, "RELIANCE.NS", [
        ("2026-10-27", 1.0),
        ("2026-10-28", 0.0),
    ])
    dates = pd.DatetimeIndex(
        pd.to_datetime(["2026-10-29", "2026-10-30"]).tz_localize("Asia/Kolkata"))
    feat = sentiment_feature("RELIANCE.NS", dates, lookback_days=3,
                             scores_root=str(tmp_path / "scores"))
    assert feat.iloc[0] == pytest.approx(0.5)   # mean of 1.0 and 0.0


def test_sentiment_feature_returns_nan_when_no_headlines(tmp_path):
    dates = pd.DatetimeIndex(
        pd.to_datetime(["2026-10-29"]).tz_localize("Asia/Kolkata"))
    feat = sentiment_feature("RELIANCE.NS", dates, lookback_days=3,
                             scores_root=str(tmp_path / "scores"))
    assert pd.isna(feat.iloc[0])


def test_sentiment_feature_lookback_window_excludes_future(tmp_path):
    """Headlines on or after `day` must not count for that day's feature."""
    _setup_sentiment(tmp_path, "RELIANCE.NS", [
        ("2026-10-29", 1.0),   # same day as query - must NOT be included
        ("2026-10-28", -1.0),  # one day before - must be included
    ])
    dates = pd.DatetimeIndex(
        pd.to_datetime(["2026-10-29"]).tz_localize("Asia/Kolkata"))
    feat = sentiment_feature("RELIANCE.NS", dates, lookback_days=3,
                             scores_root=str(tmp_path / "scores"))
    assert feat.iloc[0] == pytest.approx(-1.0)  # only the prior-day headline


def test_sentiment_feature_empty_dates(tmp_path):
    dates = pd.DatetimeIndex([])
    feat = sentiment_feature("RELIANCE.NS", dates,
                             scores_root=str(tmp_path / "scores"))
    assert feat.empty

