import pandas as pd
from src.data.storage import append_bars
from datetime import date

from src.monitor.quality import check_ticker, partial_dates

TODAY = pd.Timestamp("2024-01-16", tz="Asia/Kolkata")


def make(dates, closes, ticker="T.NS"):
    return pd.DataFrame({
        "timestamp": pd.to_datetime(dates), "ticker": ticker,
        "open": closes, "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes], "close": closes,
        "volume": 1000.0, "source": "test", "interval": "1d",
    })


def run(tmp_path, dates, closes, today=TODAY):
    append_bars(make(dates, closes), tmp_path)
    return check_ticker("T.NS", root=tmp_path, today=today)


def test_clean_data_has_no_problems(tmp_path):
    r = run(tmp_path, ["2024-01-11", "2024-01-12", "2024-01-15"], [100, 101, 102])
    assert r["problems"] == []


def test_gap_is_flagged(tmp_path):
    r = run(tmp_path, ["2024-01-01", "2024-01-02", "2024-01-15"], [100, 101, 102])
    assert any("gap" in p for p in r["problems"])


def test_jump_is_flagged(tmp_path):
    r = run(tmp_path, ["2024-01-11", "2024-01-12", "2024-01-15"], [100, 101, 150])
    assert any("jump" in p for p in r["problems"])


def test_stale_data_is_flagged(tmp_path):
    r = run(tmp_path, ["2024-01-01", "2024-01-02", "2024-01-03"], [100, 101, 102])
    assert any("stale" in p for p in r["problems"])

D = [date(2025, 3, d) for d in (17, 18, 19, 20)]


def test_shared_dates_are_not_reported():
    assert partial_dates({"A": set(D), "B": set(D), "C": set(D)}) == ({}, {})


def test_stock_missing_a_session_most_stocks_have_is_flagged():
    missing, minority = partial_dates({"A": set(D), "B": set(D), "C": set(D) - {D[1]}})
    assert missing == {"C": [D[1]]} and minority == {}


def test_date_only_a_minority_has_is_reported_not_judged():
    # the real 2025-03-18 case: one stock has the bar, the rest lack it
    rest = set(D) - {D[1]}
    missing, minority = partial_dates({"ITC": set(D), "B": rest, "C": rest})
    assert missing == {} and minority == {D[1]: ["ITC"]}


def test_dates_outside_a_stocks_own_range_are_not_gaps():
    # C starts later (new listing) and B's last bar is not in yet
    missing, minority = partial_dates({"A": set(D), "B": set(D[:3]), "C": set(D[2:])})
    assert missing == {} and minority == {}
