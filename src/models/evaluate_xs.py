import sys

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import roc_auc_score

from ..backtest.costs import get_costs
from ..backtest.engine import compute_metrics, run_backtest
from ..backtest.portfolio import run_portfolio
from ..data.schema import TZ
from ..data.storage import read_bars
from .crosssection import add_cross_section, walk_forward_xs
from .features import FEATURES, HORIZON
from .tracking import log_run
from .walkforward import PARAMS, build_panel

YEARS = [2021, 2022, 2023]     # inside train+val; the test split is never touched
N_RANDOM = 20


def load_window(tickers, start, end):
    opens, closes = {}, {}
    for t in tickers:
        d = read_bars(t, "1d").sort_values("timestamp")
        d = d[(d["timestamp"] >= start) & (d["timestamp"] <= end)].set_index("timestamp")
        opens[t], closes[t] = d["open"], d["close"]
    O, C = pd.DataFrame(opens), pd.DataFrame(closes)
    ok = O.notna().all(axis=1) & C.notna().all(axis=1)
    return O[ok], C[ok]


def main(k: int = 5, rebalance_every: int = 5,
         config_path: str = "configs/config.yaml") -> None:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    costs = get_costs(cfg)
    tickers = cfg["tickers"]
    cap_t = float(cfg.get("capital_per_ticker", 100_000))
    capital = cap_t * len(tickers)
    start = pd.Timestamp(f"{YEARS[0]}-01-01", tz=TZ)
    end = pd.Timestamp(cfg["splits"]["val_end"], tz=TZ)

    panel = add_cross_section(build_panel(tickers))
    preds = walk_forward_xs(panel, YEARS)

    aucs = {}
    print("Out-of-sample AUC, 'beats same-day median' (0.50 = coin flip):")
    for y, g in preds.dropna(subset=["target_rel"]).groupby("year"):
        aucs[y] = roc_auc_score(g["target_rel"], g["prob"])
        print(f"  {y}: {aucs[y]:.3f}")

    O, C = load_window(tickers, start, end)

    def scores(long_df, col):
        return long_df.pivot(index="timestamp", columns="ticker", values=col) \
            .reindex(index=O.index, columns=O.columns)

    def metrics(res):
        m = compute_metrics(res["equity"])
        m.update(trades=res["trades"], fees=res["fees"], slippage=res["slippage"])
        return m

    rows = {}
    rows["model_top5"] = metrics(run_portfolio(
        O, C, scores(preds, "prob"), costs, capital, k, rebalance_every))
    rows["momentum_top5"] = metrics(run_portfolio(
        O, C, scores(panel, "ret_20"), costs, capital, k, rebalance_every))

    rand = []
    for seed in range(N_RANDOM):
        rs = pd.DataFrame(np.random.default_rng(seed).random(O.shape),
                          index=O.index, columns=O.columns)
        rand.append(metrics(run_portfolio(O, C, rs, costs, capital, k, rebalance_every)))
    rand_df = pd.DataFrame(rand)
    rows[f"random_top5 (mean of {N_RANDOM})"] = rand_df.mean().to_dict()

    bh = []
    for t in tickers:
        d = pd.DataFrame({"timestamp": O.index, "open": O[t].to_numpy(),
                          "close": C[t].to_numpy()})
        bh.append(run_backtest(d, np.ones(len(d)), costs, cap_t))
    bh_m = compute_metrics(pd.concat([r["equity"] for r in bh], axis=1).sum(axis=1))
    bh_m.update(trades=sum(r["trades"] for r in bh), fees=sum(r["fees"] for r in bh),
                slippage=sum(r["slippage"] for r in bh))
    rows["buy_hold_all25"] = bh_m

    table = pd.DataFrame(rows).T
    show = table.copy()
    for c in ["total_return", "cagr", "max_drawdown"]:
        show[c] = (show[c] * 100).map("{:.1f}%".format)
    show["sharpe"] = show["sharpe"].map("{:.2f}".format)
    for c in ["trades", "fees", "slippage"]:
        show[c] = show[c].map("{:,.0f}".format)

    print(f"\nTop-{k} portfolio, rebalance every {rebalance_every} days | "
          f"{YEARS[0]}-{YEARS[-1]} | net of costs\n")
    print(show.to_string())

    beat = int((rand_df["sharpe"] < rows["model_top5"]["sharpe"]).sum())
    print(f"\nModel Sharpe beats {beat} of {N_RANDOM} random top-{k} portfolios.")
    print(f"Random Sharpe range: {rand_df['sharpe'].min():.2f} to "
          f"{rand_df['sharpe'].max():.2f}")

    log_run(f"xgb_xs_top{k}_reb{rebalance_every}",
            {**PARAMS, "experiment": "2_cross_sectional", "k": k,
             "rebalance_every": rebalance_every, "years": YEARS, "horizon": HORIZON,
             "features": FEATURES, "n_stocks": len(tickers)},
            aucs, table)


if __name__ == "__main__":
    main()