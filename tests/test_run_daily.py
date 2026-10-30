import json
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


def test_missed_days_are_replayed_in_order(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    day("buy_hold", 1)
    msg = day("buy_hold", 3)                    # day 2 was skipped, so it is replayed
    assert "replayed 2 days" in msg
    assert read_positions(tmp_path, "buy_hold") == {t: 990 for t in "ABCDE"}
    log = (tmp_path / "state" / "paper_buy_hold" / "orders.jsonl").read_text().splitlines()
    filled_days = {json.loads(x)["day"] for x in log if json.loads(x)["status"] == "filled"}
    assert filled_days == {"2024-01-02"}        # filled at day 2's open, not day 3's


def test_load_frames_drops_dates_missing_for_any_stock(monkeypatch):
    from src.paper import run_daily

    def fake_bars(t, interval, root="data/raw"):
        dates = (["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"] if t == "A"
                 else ["2024-01-01", "2024-01-03", "2024-01-04"])   # B lacks 01-02
        ts = pd.to_datetime(dates).tz_localize("Asia/Kolkata")
        return pd.DataFrame({"timestamp": ts, "open": 100.0, "close": 100.0})

    monkeypatch.setattr(run_daily, "read_bars", fake_bars)
    O, C, latest, lagging = run_daily.load_frames(["A", "B"])
    assert list(O.index) == ["2024-01-01", "2024-01-03", "2024-01-04"]
    assert latest == "2024-01-04" and lagging == []


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