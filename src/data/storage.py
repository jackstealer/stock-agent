from pathlib import Path
import pandas as pd
from .schema import validate_bars, COLUMNS


def _path(root, interval: str, ticker: str) -> Path:
    return Path(root) / interval / f"{ticker}.parquet"


def append_bars(df: pd.DataFrame, root="data/raw") -> int:
    """Validate and append new bars. Returns the number of rows actually added."""
    df = validate_bars(df)
    added = 0
    for (ticker, interval), g in df.groupby(["ticker", "interval"]):
        p = _path(root, interval, ticker)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            old = pd.read_parquet(p)
            new = g[~g["timestamp"].isin(old["timestamp"])]
            if new.empty:
                continue
            out = pd.concat([old, new])
        else:
            new, out = g, g
        out = out.sort_values("timestamp").reset_index(drop=True)
        tmp = p.with_suffix(".tmp")      # write to temp, then swap in:
        out.to_parquet(tmp, index=False)  # a crash never leaves a half-written file
        tmp.replace(p)
        added += len(new)
    return added


def read_bars(ticker: str, interval: str, root="data/raw") -> pd.DataFrame:
    p = _path(root, interval, ticker)
    if not p.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_parquet(p)