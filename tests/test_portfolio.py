import pandas as pd
import pytest

from src.backtest.costs import DEFAULT_COSTS
from src.backtest.portfolio import run_portfolio
from src.models.crosssection import add_cross_section
from src.models.features import FEATURES, add_label

ZERO = {k: 0.0 for k in DEFAULT_COSTS}


def frames(a, b):
    idx = pd.date_range("2024-01-01", periods=len(a), freq="D", tz="Asia/Kolkata")
    O = pd.DataFrame({"A": a, "B": b}, index=idx, dtype=float)
    return O, O.copy()


def scores(idx, a, b):
    return pd.DataFrame({"A": a, "B": b}, index=idx, dtype=float)


def test_trades_at_next_open_not_signal_day():
    O, C = frames([100, 110, 120, 130, 140, 150], [100] * 6)
    S = scores(O.index, [1] * 6, [0] * 6)
    r = run_portfolio(O, C, S, ZERO, 100_000, k=1, rebalance_every=5)
    # bought at day 1's open (110): 909 shares + Rs 10 cash, worth 150 at the end.
    # Buying at day 0's price of 100 would have given 150,000.
    assert r["equity"].iloc[-1] == pytest.approx(136_360)


def test_switching_names_counts_three_trades():
    O, C = frames([100] * 6, [100] * 6)
    S = scores(O.index, [1, 1, 0, 0, 0, 0], [0, 0, 1, 1, 1, 1])
    r = run_portfolio(O, C, S, ZERO, 100_000, k=1, rebalance_every=2)
    assert r["trades"] == 3                      # buy A, sell A, buy B
    assert r["equity"].iloc[-1] == pytest.approx(100_000)


def test_no_scores_means_cash():
    O, C = frames([100, 110, 120], [100, 90, 80])
    nan = scores(O.index, [float("nan")] * 3, [float("nan")] * 3)
    r = run_portfolio(O, C, nan, ZERO, 100_000, k=1)
    assert r["trades"] == 0 and (r["equity"] == 100_000).all()


def test_costs_reduce_profit():
    O, C = frames([100, 110, 120, 130, 140, 150], [100] * 6)
    S = scores(O.index, [1] * 6, [0] * 6)
    free = run_portfolio(O, C, S, ZERO, 100_000, k=1)
    paid = run_portfolio(O, C, S, DEFAULT_COSTS, 100_000, k=1)
    assert paid["equity"].iloc[-1] < free["equity"].iloc[-1]
    assert paid["fees"] > 0


def test_relative_label_beats_same_day_median():
    ts = pd.Timestamp("2024-01-01", tz="Asia/Kolkata")
    p = pd.DataFrame({"timestamp": [ts] * 3, "ticker": ["A", "B", "C"],
                      "fwd_ret": [0.01, 0.02, 0.03]})
    for f in FEATURES:
        p[f] = [1.0, 2.0, 3.0]
    out = add_cross_section(p)
    assert out["target_rel"].tolist() == [0.0, 0.0, 1.0]
    assert out["cs_ret_1"].tolist() == pytest.approx([1 / 3, 2 / 3, 1.0])


def test_forward_return_column():
    d = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=10, freq="D", tz="Asia/Kolkata"),
        "open": [100.0] * 10})
    d.loc[6, "open"] = 110.0
    assert add_label(d)["fwd_ret"].iloc[0] == pytest.approx(0.10)
    