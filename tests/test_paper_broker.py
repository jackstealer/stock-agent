import pytest

from src.backtest.costs import DEFAULT_COSTS
from src.paper.broker import PaperBroker
from src.risk import killswitch

ZERO = {k: 0.0 for k in DEFAULT_COSTS}


def make(tmp_path, costs=ZERO):
    return PaperBroker(state_dir=tmp_path / "paper", capital=100_000.0, costs=costs,
                       kill_path=tmp_path / "KILL.json")


def test_buy_fills_and_updates_state(tmp_path):
    b = make(tmp_path)
    b.mark("d1", {"A": 100.0})
    r = b.submit("d1", "A", "buy", 100, 100.0)
    assert r["status"] == "filled"
    assert b.s["cash"] == pytest.approx(90_000)
    assert b.s["positions"] == {"A": 100}


def test_costs_are_charged(tmp_path):
    b = make(tmp_path, costs=DEFAULT_COSTS)
    b.mark("d1", {"A": 100.0})
    r = b.submit("d1", "A", "buy", 100, 100.0)
    assert r["fee"] > 0 and b.s["cash"] < 90_000


def test_rejected_order_changes_nothing_and_is_logged(tmp_path):
    b = make(tmp_path)
    b.mark("d1", {"A": 100.0})
    r = b.submit("d1", "A", "buy", 300, 100.0)           # too large
    assert r["status"] == "rejected"
    assert b.s["cash"] == pytest.approx(100_000) and b.s["positions"] == {}
    assert len((tmp_path / "paper" / "orders.jsonl").read_text().splitlines()) == 1


def test_kill_switch_blocks_every_order(tmp_path):
    b = make(tmp_path)
    b.mark("d1", {"A": 100.0})
    killswitch.engage("test", tmp_path / "KILL.json")
    r = b.submit("d1", "A", "buy", 10, 100.0)
    assert r["status"] == "rejected" and "kill" in r["reason"]


def test_drawdown_trips_the_kill_switch(tmp_path):
    b = make(tmp_path)
    b.mark("d1", {"A": 100.0})
    b.submit("d1", "A", "buy", 200, 100.0)               # Rs 20k position
    reasons = b.mark("d2", {"A": 10.0})                  # equity 100k -> 82k
    assert reasons and killswitch.is_engaged(tmp_path / "KILL.json")


def test_rejection_storm_trips_the_kill_switch(tmp_path):
    b = make(tmp_path)
    b.mark("d1", {"A": 100.0})
    for _ in range(10):
        b.submit("d1", "A", "sell", 5, 100.0)            # nothing held: all rejected
    assert killswitch.is_engaged(tmp_path / "KILL.json")


def test_state_survives_a_restart(tmp_path):
    b = make(tmp_path)
    b.mark("d1", {"A": 100.0})
    b.submit("d1", "A", "buy", 100, 100.0)
    again = make(tmp_path)
    assert again.s["positions"] == {"A": 100}
    assert again.s["cash"] == pytest.approx(90_000)


def test_kill_switch_keeps_first_reason(tmp_path):
    p = tmp_path / "KILL.json"
    assert killswitch.engage("first", p) is True
    assert killswitch.engage("second", p) is False
    assert killswitch.status(p)["reason"] == "first"