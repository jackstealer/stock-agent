import json

import numpy as np
import pandas as pd
import pytest

from src.gate.check import VAR_FLOOR_DAILY, evaluate, paper_returns
from src.gate.registry import compare
from src.gate.stats import (deflated_sharpe, expected_max_sharpe, prob_sharpe,
                            sharpe_daily)


def series(mean, sd, n, seed):
    return pd.Series(np.random.default_rng(seed).normal(mean, sd, n))


def test_luck_hurdle_grows_with_trials_and_variance():
    v = VAR_FLOOR_DAILY
    assert expected_max_sharpe(1, v) == 0.0
    assert 0 < expected_max_sharpe(4, v) < expected_max_sharpe(20, v) \
        < expected_max_sharpe(100, v)
    assert expected_max_sharpe(10, 4 * v) == pytest.approx(
        2 * expected_max_sharpe(10, v))


def test_probabilistic_sharpe():
    r = series(0.002, 0.01, 1000, 0)       # true daily Sharpe 0.2: clearly positive
    assert prob_sharpe(r, 0.0) > 0.99
    assert prob_sharpe(r, sharpe_daily(r)) == pytest.approx(0.5)


def test_deflation_gets_harsher_with_more_trials():
    r = series(0.0008, 0.01, 800, 1)
    assert deflated_sharpe(r, 2, VAR_FLOOR_DAILY) > deflated_sharpe(r, 100, VAR_FLOOR_DAILY)


def test_pure_noise_is_not_promoted():
    r = series(0.0, 0.01, 1000, 0)
    assert deflated_sharpe(r, 20, VAR_FLOOR_DAILY) < 0.95


def test_registry_comparison():
    reg = ["a", "b", "b"]
    assert compare(reg, ["a", "b", "b"]) == []
    assert any("not in the registry" in p for p in compare(reg, ["a", "b", "b", "c"]))
    assert any("fewer" in p for p in compare(reg, ["a", "b"]))


def make_pair(active_mean, n, seed):
    bench = series(0.0004, 0.01, n, seed)
    return bench + series(active_mean, 0.005, n, seed + 1), bench


def test_real_edge_passes_every_check():
    strat, bench = make_pair(0.0015, 600, 1)
    checks = evaluate(strat, bench, n_trials=4, registry_problems=[])
    assert all(ok for _, ok in checks)


def test_noise_with_many_trials_fails_the_deflated_sharpe_check():
    strat, bench = make_pair(0.0, 600, 2)
    checks = evaluate(strat, bench, n_trials=50, registry_problems=[])
    assert checks[2][1] is False


def test_short_history_and_registry_problems_fail():
    strat, bench = make_pair(0.0015, 100, 3)
    assert evaluate(strat, bench, 4, [])[1][1] is False
    assert evaluate(*make_pair(0.0015, 600, 1), 4, ["hidden run"])[0][1] is False


def test_paper_returns_use_the_last_mark_of_each_day(tmp_path):
    d = tmp_path / "paper_x"
    d.mkdir()
    rows = [{"day": "d1", "equity": 100.0}, {"day": "d2", "equity": 90.0},
            {"day": "d2", "equity": 110.0}, {"day": "d3", "equity": 121.0}]
    (d / "equity.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    r = paper_returns("x", root=tmp_path)
    assert r.tolist() == pytest.approx([0.10, 0.10])