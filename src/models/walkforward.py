import pandas as pd
import xgboost as xgb

from ..data.schema import TZ
from ..data.storage import read_bars
from .features import FEATURES, add_features, add_label

# Deliberately small and conservative: shallow trees, strong regularization
PARAMS = dict(n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8,
              colsample_bytree=0.8, min_child_weight=50, random_state=42, n_jobs=4)


def build_panel(tickers: list) -> pd.DataFrame:
    frames = []
    for t in tickers:
        d = add_label(add_features(read_bars(t, "1d")))
        d["ticker"] = t
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def walk_forward(panel: pd.DataFrame, test_years: list) -> pd.DataFrame:
    """For each year: train on everything whose label was fully known BEFORE the
    year began (this purges rows whose 5-day outcome spills into the test year),
    then predict that year. One model is shared across all stocks."""
    out = []
    for year in test_years:
        start = pd.Timestamp(f"{year}-01-01", tz=TZ)
        end = pd.Timestamp(f"{year + 1}-01-01", tz=TZ)
        train = panel[panel["label_end"] < start].dropna(subset=FEATURES + ["target"])
        test = panel[(panel["timestamp"] >= start) & (panel["timestamp"] < end)] \
            .dropna(subset=FEATURES)
        model = xgb.XGBClassifier(**PARAMS)
        model.fit(train[FEATURES], train["target"].astype(int))
        res = test[["ticker", "timestamp", "target"]].copy()
        res["prob"] = model.predict_proba(test[FEATURES])[:, 1]
        res["year"] = year
        out.append(res)
    return pd.concat(out, ignore_index=True)
    