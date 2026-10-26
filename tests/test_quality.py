import pandas as pd
from src.data.storage import append_bars
from src.monitor.quality import check_ticker

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