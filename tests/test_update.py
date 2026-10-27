import pandas as pd

from src.data.storage import append_bars, read_bars
from src.data.update import find_revisions, update_ticker


def make(dates, closes, ticker="T.NS"):
    return pd.DataFrame({
        "timestamp": pd.to_datetime(dates), "ticker": ticker,
        "open": closes, "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes], "close": closes,
        "volume": 1000.0, "source": "test", "interval": "1d"})


def test_find_revisions_flags_big_changes_only():
    old = make(["2024-01-01", "2024-01-02"], [100.0, 101.0])
    tiny = make(["2024-01-01", "2024-01-02"], [100.01, 101.0])
    big = make(["2024-01-01", "2024-01-02"], [50.0, 50.5])
    assert find_revisions(old, tiny) == []
    assert len(find_revisions(old, big)) == 2


def test_update_appends_only_new_days(tmp_path):
    append_bars(make(["2024-01-01", "2024-01-02"], [100.0, 101.0]), tmp_path)
    fake = lambda t, s: make(["2024-01-02", "2024-01-03"], [101.0, 102.0], ticker=t)
    r = update_ticker("T.NS", root=tmp_path, fetch=fake)
    assert r["added"] == 1 and r["revisions"] == []
    assert len(read_bars("T.NS", "1d", tmp_path)) == 3


def test_revised_history_blocks_appending(tmp_path):
    append_bars(make(["2024-01-01", "2024-01-02"], [100.0, 101.0]), tmp_path)
    # a 2:1 split halves every past price in the freshly fetched data
    fake = lambda t, s: make(["2024-01-02", "2024-01-03"], [50.5, 51.0], ticker=t)
    r = update_ticker("T.NS", root=tmp_path, fetch=fake)
    assert r["added"] == 0 and r["revisions"]
    assert len(read_bars("T.NS", "1d", tmp_path)) == 2