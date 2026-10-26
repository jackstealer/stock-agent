import pandas as pd
import pytest

from src.backtest.costs import DEFAULT_COSTS, trade_cost
from src.backtest.engine import run_backtest
from src.backtest.splits import get_split

ZERO = {k: 0.0 for k in DEFAULT_COSTS}


def make(prices):
    idx = pd.date_range("2024-01-01", periods=len(prices), freq="D",
                        tz="Asia/Kolkata")
    p = [float(x) for x in prices]
    return pd.DataFrame({"timestamp": idx, "open": p, "close": p})


def test_no_signal_stays_flat():
    res = run_backtest(make([100, 110, 120, 130]), [0, 0, 0, 0], ZERO)
    assert (res["equity"] == 100_000).all()
    assert res["trades"] == 0


def test_fills_at_next_open_not_signal_close():
    # Signal on day 0 (close 100) must buy at day 1's open (110):
    # 909 shares, Rs 10 cash left, worth 130 at the end -> 118,180.
    # Buying at 100 would have given 130,000.
    res = run_backtest(make([100, 110, 120, 130]), [1, 1, 1, 1], ZERO)
    assert res["equity"].iloc[-1] == pytest.approx(118_180)


def test_costs_reduce_profit():
    free = run_backtest(make([100, 110, 120, 130]), [1, 1, 1, 1], ZERO)
    paid = run_backtest(make([100, 110, 120, 130]), [1, 1, 1, 1], DEFAULT_COSTS)
    assert paid["equity"].iloc[-1] < free["equity"].iloc[-1]
    assert paid["fees"] > 0 and paid["slippage"] > 0


def test_round_trip_counts_two_trades():
    res = run_backtest(make([100, 100, 100, 100]), [1, 1, 0, 0], ZERO)
    assert res["trades"] == 2
    assert res["equity"].iloc[-1] == pytest.approx(100_000)


def test_cost_function_is_sensible():
    buy = trade_cost(100_000, "buy", DEFAULT_COSTS)
    sell = trade_cost(100_000, "sell", DEFAULT_COSTS)
    assert buy > sell                  # stamp duty is buy-side only
    assert 100 < buy < 200             # roughly 0.14% of Rs 1 lakh


def test_test_split_is_locked():
    cfg = {"splits": {"train_end": "2024-01-03", "val_end": "2024-01-05"}}
    df = make(range(1, 11))
    with pytest.raises(PermissionError):
        get_split(df, cfg, "test")
    assert len(get_split(df, cfg, "train")) == 3
    assert len(get_split(df, cfg, "val")) == 2
    assert len(get_split(df, cfg, "test", allow_test=True)) == 5