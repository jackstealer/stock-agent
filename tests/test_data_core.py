import pandas as pd
import pytest
from src.data.schema import validate_bars
from src.data.storage import append_bars, read_bars


def bars(dates, close=100.0, ticker="TEST.NS"):
    return pd.DataFrame({
        "timestamp": pd.to_datetime(dates),
        "ticker": ticker,
        "open": close, "high": close + 1, "low": close - 1, "close": close,
        "volume": 1000.0, "source": "test", "interval": "1d",
    })


def test_valid_batch_passes():
    out = validate_bars(bars(["2024-01-01", "2024-01-02"]))
    assert len(out) == 2
    assert str(out["timestamp"].dt.tz) == "Asia/Kolkata"


@pytest.mark.parametrize("col,val", [
    ("close", -5.0), ("volume", -1.0), ("open", 0.0), ("high", 50.0),
])
def test_bad_values_rejected(col, val):
    df = bars(["2024-01-01"])
    df[col] = val
    with pytest.raises(ValueError):
        validate_bars(df)


def test_duplicate_rows_in_batch_rejected():
    with pytest.raises(ValueError):
        validate_bars(bars(["2024-01-01", "2024-01-01"]))


def test_append_adds_only_new_rows(tmp_path):
    assert append_bars(bars(["2024-01-01", "2024-01-02"]), tmp_path) == 2
    assert append_bars(bars(["2024-01-02", "2024-01-03"]), tmp_path) == 1
    assert len(read_bars("TEST.NS", "1d", tmp_path)) == 3


def test_history_is_never_overwritten(tmp_path):
    append_bars(bars(["2024-01-01"], close=100.0), tmp_path)
    append_bars(bars(["2024-01-01"], close=999.0), tmp_path)  # same date, new value
    assert read_bars("TEST.NS", "1d", tmp_path)["close"].iloc[0] == 100.0