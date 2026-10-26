import pandas as pd
from src.data.sources import eod
from src.data.schema import validate_bars


def fake_download(*args, **kwargs):
    idx = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
    cols = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Adj Close", "Volume"], ["TEST.NS"]])
    data = [[100, 101, 99, 100, 100, 1000],
            [101, 102, 100, 101, 101, 2000],
            [None, None, None, None, None, None]]   # junk row must be dropped
    return pd.DataFrame(data, index=idx, columns=cols)


def test_fetch_eod_formats_rows(monkeypatch):
    monkeypatch.setattr(eod.yf, "download", fake_download)
    df = eod.fetch_eod("TEST.NS", "2024-01-01", "2024-01-04")
    out = validate_bars(df)
    assert len(out) == 2
    assert set(out["interval"]) == {"1d"}
    assert set(out["source"]) == {"yfinance"}


def test_empty_download_returns_empty_frame(monkeypatch):
    monkeypatch.setattr(eod.yf, "download", lambda *a, **k: pd.DataFrame())
    assert eod.fetch_eod("TEST.NS", "2024-01-01").empty
def test_placeholder_bars_are_dropped(monkeypatch):
    def fake(*args, **kwargs):
        idx = pd.to_datetime(["2024-01-01", "2024-01-02"])
        cols = pd.MultiIndex.from_product(
            [["Open", "High", "Low", "Close", "Adj Close", "Volume"], ["TEST.NS"]])
        data = [[100, 101, 99, 100, 100, 1000],
                [100, 100, 100, 100, 100, 0]]     # flat + zero volume = placeholder
        return pd.DataFrame(data, index=idx, columns=cols)

    monkeypatch.setattr(eod.yf, "download", fake)
    df = eod.fetch_eod("TEST.NS", "2024-01-01", "2024-01-03")
    assert len(df) == 1