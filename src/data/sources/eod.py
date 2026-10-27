import pandas as pd
import yfinance as yf

from ..schema import COLUMNS, TZ

def default_end(now=None) -> str:
    """End date (exclusive) for yfinance. After 18:00 IST on a weekday the day's
    bar is treated as final and included. Before that it is excluded, because it
    would be an unfinished candle."""
    now = now if now is not None else pd.Timestamp.now(tz=TZ)
    include_today = now.weekday() < 5 and now.hour >= 18
    return (now + pd.Timedelta(days=int(include_today))).strftime("%Y-%m-%d")

def fetch_eod(ticker: str, start: str, end: str | None = None) -> pd.DataFrame:
    """Download daily bars and return them in our standard row format.
    `end` is exclusive and defaults to today (IST), so today's bar,
    which is incomplete until the market closes, is never fetched."""
    if end is None:
        end = default_end()

    raw = yf.download(ticker, start=start, end=end, interval="1d",
                      auto_adjust=False, progress=False)
    if raw is None or raw.empty:
        return pd.DataFrame(columns=COLUMNS)

    if isinstance(raw.columns, pd.MultiIndex):      # newer yfinance versions
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.dropna(subset=["Open", "High", "Low", "Close"])
        # Yahoo fills days the market was closed with flat, zero-volume placeholder bars
    placeholder = ((raw["Volume"] == 0) & (raw["Open"] == raw["High"])
                   & (raw["High"] == raw["Low"]) & (raw["Low"] == raw["Close"]))
    raw = raw[~placeholder]

    return pd.DataFrame({
        "timestamp": raw.index,
        "ticker": ticker,
        "open": raw["Open"].to_numpy(),
        "high": raw["High"].to_numpy(),
        "low": raw["Low"].to_numpy(),
        "close": raw["Close"].to_numpy(),
        "volume": raw["Volume"].to_numpy(),
        "source": "yfinance",
        "interval": "1d",
    })