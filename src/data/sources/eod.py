import pandas as pd
import yfinance as yf

from ..schema import COLUMNS, TZ


def fetch_eod(ticker: str, start: str, end: str | None = None) -> pd.DataFrame:
    """Download daily bars and return them in our standard row format.
    `end` is exclusive and defaults to today (IST), so today's bar,
    which is incomplete until the market closes, is never fetched."""
    if end is None:
        end = pd.Timestamp.now(tz=TZ).strftime("%Y-%m-%d")

    raw = yf.download(ticker, start=start, end=end, interval="1d",
                      auto_adjust=False, progress=False)
    if raw is None or raw.empty:
        return pd.DataFrame(columns=COLUMNS)

    if isinstance(raw.columns, pd.MultiIndex):      # newer yfinance versions
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.dropna(subset=["Open", "High", "Low", "Close"])

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