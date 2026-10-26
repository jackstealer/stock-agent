import numpy as np
import pandas as pd


def buy_and_hold(df: pd.DataFrame) -> pd.Series:
    return pd.Series(1, index=df.index)


def ma_crossover(df: pd.DataFrame, fast: int = 20, slow: int = 100) -> pd.Series:
    """Hold when the fast average is above the slow one. Uses only past closes."""
    f = df["close"].rolling(fast).mean()
    s = df["close"].rolling(slow).mean()
    return (f > s).astype(int)          # NaN warm-up period counts as flat


def random_signal(df: pd.DataFrame, seed: int, flip_prob: float = 0.02) -> pd.Series:
    """Random in/out, flipping with ~2% chance per day (about 50-day holds)."""
    rng = np.random.default_rng(seed)
    flips = rng.random(len(df)) < flip_prob
    return pd.Series(np.cumsum(flips) % 2, index=df.index)