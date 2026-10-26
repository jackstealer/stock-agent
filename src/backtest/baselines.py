import sys

import pandas as pd
import yaml

from ..data.storage import read_bars
from .costs import get_costs
from .engine import compute_metrics, run_backtest
from .splits import get_split
from .strategies import buy_and_hold, ma_crossover, random_signal

N_RANDOM = 5


def signals_for(full: pd.DataFrame) -> dict:
    sigs = {"buy_hold": buy_and_hold(full), "ma_20_100": ma_crossover(full)}
    for seed in range(N_RANDOM):
        sigs[f"random_{seed}"] = random_signal(full, seed)
    return sigs


def main(part: str = "val", config_path: str = "configs/config.yaml") -> None:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    costs = get_costs(cfg)
    capital = float(cfg.get("capital_per_ticker", 100_000))

    curves, fees, slip, trades = {}, {}, {}, {}
    for ticker in cfg["tickers"]:
        full = read_bars(ticker, "1d").sort_values("timestamp").reset_index(drop=True)
        window = get_split(full, cfg, part)
        for name, sig in signals_for(full).items():   # signals use full history,
            res = run_backtest(window, sig.loc[window.index], costs, capital)
            curves.setdefault(name, []).append(res["equity"])  # trading uses window only
            fees[name] = fees.get(name, 0) + res["fees"]
            slip[name] = slip.get(name, 0) + res["slippage"]
            trades[name] = trades.get(name, 0) + res["trades"]

    rows = {}
    for name, eqs in curves.items():
        portfolio = pd.concat(eqs, axis=1).ffill().dropna().sum(axis=1)
        m = compute_metrics(portfolio)
        m.update(trades=trades[name], fees=fees[name], slippage=slip[name])
        rows[name] = m
    table = pd.DataFrame(rows).T

    rand = table[table.index.str.startswith("random_")]
    out = table.drop(rand.index)
    out.loc[f"random (mean of {N_RANDOM})"] = rand.mean()
    out.loc[f"random (best of {N_RANDOM})"] = rand.loc[rand["total_return"].idxmax()]

    show = out.copy()
    for c in ["total_return", "cagr", "max_drawdown"]:
        show[c] = (show[c] * 100).map("{:.1f}%".format)
    show["sharpe"] = show["sharpe"].map("{:.2f}".format)
    for c in ["trades", "fees", "slippage"]:
        show[c] = show[c].map("{:,.0f}".format)

    n = len(cfg["tickers"])
    print(f"\nSplit: {part} | {n} stocks x Rs {capital:,.0f} each, equal weight, "
          f"net of costs\n")
    print(show.to_string())


if __name__ == "__main__":
    part = sys.argv[1] if len(sys.argv) > 1 else "val"
    main(part)