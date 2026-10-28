import json

import pandas as pd
import pytest

from src.monitor.report import account_summary, drawdown, equity_curve, recent_orders


def make_account(tmp_path, name="x"):
    d = tmp_path / f"paper_{name}"
    d.mkdir()
    rows = [{"day": "2024-01-02", "equity": 100.0}, {"day": "2024-01-03", "equity": 90.0},
            {"day": "2024-01-03", "equity": 110.0}, {"day": "2024-01-04", "equity": 99.0}]
    (d / "equity.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    (d / "state.json").write_text(json.dumps(
        {"cash": 50.0, "positions": {"A": 3}, "orders_today": 2, "rejected_today": 1}))
    (d / "runner.json").write_text(json.dumps(
        {"initial": 100.0, "last_run_day": "2024-01-04"}))
    return d


def test_equity_curve_takes_the_last_mark_of_each_day(tmp_path):
    make_account(tmp_path)
    s = equity_curve("x", tmp_path)
    assert s.tolist() == [100.0, 110.0, 99.0]
    assert s.index.is_monotonic_increasing


def test_drawdown_is_never_positive():
    s = pd.Series([100.0, 110.0, 99.0, 120.0])
    dd = drawdown(s)
    assert dd.max() == 0.0 and dd.iloc[2] == pytest.approx(-0.10)


def test_account_summary(tmp_path):
    d = make_account(tmp_path)
    s = account_summary("x", tmp_path)
    assert s["equity"] == 99.0 and s["holdings"] == 1 and s["initial"] == 100.0
    assert s["killed"] is False
    (d / "KILL.json").write_text("{}")
    assert account_summary("x", tmp_path)["killed"] is True


def test_missing_account_and_empty_orders_are_handled(tmp_path):
    assert account_summary("nope", tmp_path) == {}
    assert equity_curve("nope", tmp_path).empty
    assert recent_orders("nope", tmp_path).empty


def test_recent_orders_newest_first_and_limited(tmp_path):
    d = tmp_path / "paper_x"
    d.mkdir()
    rows = [{"day": f"d{i}", "ticker": "A", "side": "buy", "qty": 1, "status": "filled"}
            for i in range(5)]
    (d / "orders.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    out = recent_orders("x", tmp_path, n=3)
    assert out["day"].tolist() == ["d4", "d3", "d2"]