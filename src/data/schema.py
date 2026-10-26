import pandas as pd

COLUMNS = ["timestamp", "ticker", "open", "high", "low", "close",
           "volume", "source", "interval"]
VALID_INTERVALS = {"1d", "5m", "1m", "tick"}
TZ = "Asia/Kolkata"


def validate_bars(df: pd.DataFrame) -> pd.DataFrame:
    """Check a batch of bars; return a clean copy in IST, sorted by time.
    Raises ValueError on anything suspicious: bad data never gets stored."""
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")

    df = df[COLUMNS].copy()
    if df.empty:
        return df

    ts = pd.to_datetime(df["timestamp"])
    df["timestamp"] = ts.dt.tz_localize(TZ) if ts.dt.tz is None else ts.dt.tz_convert(TZ)

    num = ["open", "high", "low", "close", "volume"]
    df[num] = df[num].apply(pd.to_numeric, errors="raise")
    if df[num].isna().any().any():
        raise ValueError("NaN in price/volume columns")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("non-positive price")
    if (df["volume"] < 0).any():
        raise ValueError("negative volume")
    if (df["high"] < df["low"]).any():
        raise ValueError("high < low")
    if (df["high"] < df[["open", "close"]].max(axis=1)).any() or \
       (df["low"] > df[["open", "close"]].min(axis=1)).any():
        raise ValueError("open/close outside the high-low range")
    if not set(df["interval"]).issubset(VALID_INTERVALS):
        raise ValueError(f"bad interval, allowed: {VALID_INTERVALS}")
    if df.duplicated(["ticker", "interval", "timestamp"]).any():
        raise ValueError("duplicate (ticker, interval, timestamp) in batch")

    return df.sort_values("timestamp").reset_index(drop=True)