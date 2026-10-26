import numpy as np
import pandas as pd

from src.models.features import FEATURES, add_features, add_label


def synthetic(n=300):
    rng = np.random.default_rng(0)
    c = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({
        "timestamp": pd.date_range("2022-01-01", periods=n, freq="D", tz="Asia/Kolkata"),
        "open": c, "high": c + 1, "low": c - 1, "close": c,
        "volume": rng.uniform(1000, 2000, n)})


def test_features_use_only_the_past():
    d = synthetic()
    d2 = d.copy()
    d2.loc[250:, ["open", "high", "low", "close", "volume"]] *= 3   # change the future
    a, b = add_features(d), add_features(d2)
    pd.testing.assert_frame_equal(a.loc[:249, FEATURES], b.loc[:249, FEATURES])


def test_label_uses_next_open_and_open_five_days_later():
    d = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=10, freq="D", tz="Asia/Kolkata"),
        "open": [100.0] * 10})
    d.loc[6, "open"] = 110.0
    out = add_label(d)
    assert out["target"].iloc[0] == 1.0        # entry open[1]=100, exit open[6]=110
    assert out["target"].iloc[1] == 0.0
    assert out["target"].iloc[4:].isna().all() # outcome not known yet