import numpy as np
import pandas as pd

from .costs import trade_cost


def run_portfolio(opens: pd.DataFrame, closes: pd.DataFrame, scores: pd.DataFrame,
                  costs: dict, capital: float, k: int = 5,
                  rebalance_every: int = 5) -> dict:
    """Long-only top-k portfolio. All frames are (dates x tickers) with identical
    index and columns. scores.iloc[t] is known at the close of day t and is traded
    at the NEXT day's open. Names that stay in the top k are left alone."""
    O, C, S = (x.to_numpy(float) for x in (opens, closes, scores))
    slip = costs["slippage_pct"] / 100
    n, m = O.shape
    cash = float(capital)
    shares = np.zeros(m, dtype=int)
    fees = slippage_cost = 0.0
    trades = 0
    equity = np.empty(n)
    first = None

    for j in range(n):
        if j > 0 and not np.isnan(S[j - 1]).all():
            if first is None:
                first = j
            if (j - first) % rebalance_every == 0:
                s = S[j - 1]
                valid = np.where(~np.isnan(s))[0]
                order = valid[np.argsort(-s[valid], kind="stable")]
                top = order[:k]
                keep = set(top.tolist())

                for t in range(m):                       # sell what dropped out
                    if shares[t] > 0 and t not in keep:
                        px = O[j, t] * (1 - slip)
                        fee = trade_cost(shares[t] * px, "sell", costs)
                        cash += shares[t] * px - fee
                        fees += fee
                        slippage_cost += shares[t] * O[j, t] * slip
                        shares[t] = 0
                        trades += 1

                new = [t for t in top if shares[t] == 0]  # buy what moved in
                if new:
                    budget = cash / len(new)
                    for t in new:
                        px = O[j, t] * (1 + slip)
                        qty = int(budget // px)
                        while qty > 0 and qty * px + trade_cost(qty * px, "buy", costs) > budget:
                            qty -= 1
                        if qty > 0:
                            fee = trade_cost(qty * px, "buy", costs)
                            cash -= qty * px + fee
                            fees += fee
                            slippage_cost += qty * O[j, t] * slip
                            shares[t] = qty
                            trades += 1
        equity[j] = cash + float((shares * C[j]).sum())

    return {"equity": pd.Series(equity, index=opens.index),
            "trades": trades, "fees": fees, "slippage": slippage_cost}