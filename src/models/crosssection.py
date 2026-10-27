import numpy as np
import pandas as pd
import xgboost as xgb

from ..data.schema import TZ
from .features import FEATURES
from .walkforward import PARAMS

CS_FEATURES = [f"cs_{f}" for f in FEATURES]


def add_cross_section(panel: pd.DataFrame) -> pd.DataFrame:
    """Relative label + same-day percentile-rank features. Uses only same-day
    cross-section information, so features stay free of future data."""
    p = panel.copy()
    med = p.groupby("timestamp")["fwd_ret"].transform("median")
    p["target_rel"] = np.where(p["fwd_ret"].isna(), np.nan,
                               (p["fwd_ret"] > med).astype(float))
    for f in FEATURES:
        p[f"cs_{f}"] = p.groupby("timestamp")[f].rank(pct=True)
    return p


def walk_forward_xs(panel: pd.DataFrame, test_years: list) -> pd.DataFrame:
    """Per year: train on rows whose 5-day outcome was fully known before the
    year began (purged), then score that year. One model for all stocks."""
    out = []
    for year in test_years:
        start = pd.Timestamp(f"{year}-01-01", tz=TZ)
        end = pd.Timestamp(f"{year + 1}-01-01", tz=TZ)
        train = panel[panel["label_end"] < start] \
            .dropna(subset=CS_FEATURES + ["target_rel"])
        test = panel[(panel["timestamp"] >= start) & (panel["timestamp"] < end)] \
            .dropna(subset=CS_FEATURES)
        model = xgb.XGBClassifier(**PARAMS)
        model.fit(train[CS_FEATURES], train["target_rel"].astype(int))
        res = test[["ticker", "timestamp", "target_rel"]].copy()
        res["prob"] = model.predict_proba(test[CS_FEATURES])[:, 1]
        res["year"] = year
        out.append(res)
    return pd.concat(out, ignore_index=True)