import numpy as np
import pandas as pd

from .costs import trade_cost


def run_backtest(df: pd.DataFrame, signal, costs: dict,
                 capital: float = 100_000.0) -> dict:
    """Long-only, one stock. `signal` is 1 (hold) or 0 (flat) per bar, decided at
    that bar's close and executed at the NEXT bar's open."""
    df = df.reset_index(drop=True)
    sig = np.nan_to_num(np.asarray(signal, dtype=float), nan=0.0)
    open_ = df["open"].to_numpy(float)
    close = df["close"].to_numpy(float)
    slip = costs["slippage_pct"] / 100

    cash, shares = capital, 0
    fees = slippage_cost = 0.0
    trades = 0
    equity = np.empty(len(df))

    for i in range(len(df)):
        if i > 0:
            want_long = sig[i - 1] > 0.5
            if want_long and shares == 0:
                px = open_[i] * (1 + slip)
                qty = int(cash // px)
                while qty > 0 and qty * px + trade_cost(qty * px, "buy", costs) > cash:
                    qty -= 1
                if qty > 0:
                    fee = trade_cost(qty * px, "buy", costs)
                    cash -= qty * px + fee
                    shares = qty
                    fees += fee
                    slippage_cost += qty * open_[i] * slip
                    trades += 1
            elif not want_long and shares > 0:
                px = open_[i] * (1 - slip)
                fee = trade_cost(shares * px, "sell", costs)
                cash += shares * px - fee
                fees += fee
                slippage_cost += shares * open_[i] * slip
                shares = 0
                trades += 1
        equity[i] = cash + shares * close[i]   # mark to market at the close

    return {"equity": pd.Series(equity, index=df["timestamp"]),
            "trades": trades, "fees": fees, "slippage": slippage_cost}


def compute_metrics(equity: pd.Series) -> dict:
    ret = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    growth = equity.iloc[-1] / equity.iloc[0]
    return {
        "total_return": growth - 1,
        "cagr": growth ** (1 / years) - 1 if years > 0 else float("nan"),
        "sharpe": ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0.0,
        "max_drawdown": (equity / equity.cummax() - 1).min(),
    }