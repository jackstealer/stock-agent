import sys

import pandas as pd
import yaml
from sklearn.metrics import roc_auc_score

from ..backtest.baselines import signals_for
from ..backtest.costs import get_costs
from ..backtest.engine import compute_metrics, run_backtest
from ..data.schema import TZ
from ..data.storage import read_bars
from .features import FEATURES, HORIZON, THRESHOLD
from .tracking import log_run
from .walkforward import PARAMS, build_panel, walk_forward

YEARS = [2021, 2022, 2023]     # all inside train+val; the test split is never touched


def fmt(table: pd.DataFrame) -> pd.DataFrame:
    s = table.copy()
    for c in ["total_return", "cagr", "max_drawdown", "invested"]:
        s[c] = (s[c] * 100).map("{:.1f}%".format)
    s["sharpe"] = s["sharpe"].map("{:.2f}".format)
    for c in ["trades", "fees", "slippage"]:
        s[c] = s[c].map("{:,.0f}".format)
    return s


def main(threshold: float = 0.5, config_path: str = "configs/config.yaml") -> None:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    costs = get_costs(cfg)
    capital = float(cfg.get("capital_per_ticker", 100_000))
    start = pd.Timestamp(f"{YEARS[0]}-01-01", tz=TZ)
    end = pd.Timestamp(cfg["splits"]["val_end"], tz=TZ)

    panel = build_panel(cfg["tickers"])
    print(f"Base rate of label=1 (up >0.5% in 5 days): {panel['target'].mean():.1%}")
    preds = walk_forward(panel, YEARS)

    aucs = {}
    print("\nOut-of-sample AUC by year (0.50 = coin flip):")
    for y, g in preds.dropna(subset=["target"]).groupby("year"):
        aucs[y] = roc_auc_score(g["target"], g["prob"])
        print(f"  {y}: {aucs[y]:.3f}")

    acc = {}
    for t in cfg["tickers"]:
        full = read_bars(t, "1d").sort_values("timestamp").reset_index(drop=True)
        window = full[(full["timestamp"] >= start) & (full["timestamp"] <= end)]
        sigs = signals_for(full)
        p = preds[preds["ticker"] == t].set_index("timestamp")["prob"]
        sigs["model"] = (full["timestamp"].map(p) > threshold).astype(int)
        for name, sig in sigs.items():
            s = sig.loc[window.index]
            res = run_backtest(window, s, costs, capital)
            a = acc.setdefault(name, {"curves": [], "fees": 0.0, "slip": 0.0,
                                      "trades": 0, "inv": []})
            a["curves"].append(res["equity"])
            a["fees"] += res["fees"]
            a["slip"] += res["slippage"]
            a["trades"] += res["trades"]
            a["inv"].append(float(s.mean()))

    rows = {}
    for name, a in acc.items():
        port = pd.concat(a["curves"], axis=1).ffill().dropna().sum(axis=1)
        m = compute_metrics(port)
        m.update(trades=a["trades"], fees=a["fees"], slippage=a["slip"],
                 invested=sum(a["inv"]) / len(a["inv"]))
        rows[name] = m
    table = pd.DataFrame(rows).T
    rand = table[table.index.str.startswith("random_")]
    out = table.drop(rand.index)
    out.loc["random (mean of 5)"] = rand.mean()

    print(f"\nWalk-forward {YEARS[0]}-{YEARS[-1]} | signal when prob > {threshold} | "
          f"net of costs\n")
    print(fmt(out).to_string())

    log_run(f"xgb_thr{threshold}",
            {**PARAMS, "threshold": threshold, "years": YEARS, "horizon": HORIZON,
             "label_threshold": THRESHOLD, "features": FEATURES,
             "n_stocks": len(cfg["tickers"])},
            aucs, out)


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 0.5)
    