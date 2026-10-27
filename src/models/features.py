import numpy as np
import pandas as pd

FEATURES = ["ret_1", "ret_5", "ret_10", "ret_20", "vol_20",
            "dist_sma50", "dist_sma200", "rsi_14", "vol_ratio", "range_pct"]
HORIZON = 5         # hold for 5 trading days
THRESHOLD = 0.005   # label = 1 if that trade gains more than 0.5%


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Every feature at row t uses data up to and including the close of day t."""
    d = df.sort_values("timestamp").reset_index(drop=True).copy()
    c = d["close"]
    for n in (1, 5, 10, 20):
        d[f"ret_{n}"] = c.pct_change(n)
    d["vol_20"] = c.pct_change().rolling(20).std()
    d["dist_sma50"] = c / c.rolling(50).mean() - 1
    d["dist_sma200"] = c / c.rolling(200).mean() - 1
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    d["rsi_14"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    d["vol_ratio"] = d["volume"] / d["volume"].rolling(20).mean()
    d["range_pct"] = (d["high"] - d["low"]) / c
    return d


def add_label(d: pd.DataFrame) -> pd.DataFrame:
    """Label at row t = did buying at tomorrow's open and selling 5 days later
    gain more than THRESHOLD? Same timing the backtester uses.
    `fwd_ret` is that trade's return; `label_end` is when the outcome becomes
    known, which we need for purging."""
    entry = d["open"].shift(-1)
    exit_ = d["open"].shift(-(HORIZON + 1))
    d["fwd_ret"] = exit_ / entry - 1
    d["target"] = (d["fwd_ret"] > THRESHOLD).astype(float)
    d.loc[d["fwd_ret"].isna(), "target"] = np.nan
    d["label_end"] = d["timestamp"].shift(-(HORIZON + 1))
    return d