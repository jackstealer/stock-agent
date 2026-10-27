import pandas as pd

from src.backtest.costs import DEFAULT_COSTS
from src.paper.run_daily import momentum_top5, run_account
from src.risk import killswitch

ZERO = {k: 0.0 for k in DEFAULT_COSTS}
CFG = {"tickers": list("ABCDE"), "capital_per_ticker": 100_000, "costs": ZERO}


def frames(n_days=5, tickers="ABCDE"):
    idx = [f"2024-01-0{i}" for i in range(1, n_days + 1)]
    O = pd.DataFrame(100.0, index=idx, columns=list(tickers))
    return O, O.copy()


def day(name, n):
    """Run as if the data ended on trading day n."""
    O, C = frames()
    return run_account(name, O.iloc[:n], C.iloc[:n], O.index[n - 1], CFG,
                       lambda m: None)


def read_positions(tmp_path, name):
    import json
    s = json.loads((tmp_path / "state" / f"paper_{name}" / "state.json").read_text())
    return s["positions"]


def test_signal_then_fill_at_next_open(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    day("buy_hold", 1)                       # decide at day 1's close
    assert read_positions(tmp_path, "buy_hold") == {}
    day("buy_hold", 2)                       # fill at day 2's open
    assert read_positions(tmp_path, "buy_hold") == {t: 990 for t in "ABCDE"}


def test_running_twice_the_same_day_does_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    day("buy_hold", 1)
    assert "already ran" in day("buy_hold", 1)


def test_missed_day_expires_pending_orders(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    day("buy_hold", 1)
    msg = day("buy_hold", 3)                 # day 2 was skipped
    assert "expired" in msg
    assert read_positions(tmp_path, "buy_hold") == {}


def test_global_kill_switch_stops_fills(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    day("buy_hold", 1)
    killswitch.engage("test")
    msg = day("buy_hold", 2)
    assert "HALTED" in msg
    assert read_positions(tmp_path, "buy_hold") == {}


def test_momentum_picks_top5_and_respects_cadence():
    ret = pd.Series({"A": .1, "B": .5, "C": .3, "D": -.1, "E": .2, "F": .4, "G": .0})
    ctx = {"ret_20": ret, "runs_since_rebalance": 999}
    assert set(momentum_top5(ctx)) == {"B", "F", "C", "E", "A"}
    assert momentum_top5({**ctx, "runs_since_rebalance": 2}) is None