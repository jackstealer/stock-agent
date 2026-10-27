import pytest

from src.risk.limits import RiskLimits, check_order, kill_reasons

L = RiskLimits()


def state(**kw):
    s = {"equity": 100_000.0, "cash": 100_000.0, "positions": {}, "prices": {},
         "orders_today": 0, "rejected_today": 0, "day_start_equity": 100_000.0,
         "peak_equity": 100_000.0}
    s.update(kw)
    return s


def order(side="buy", qty=100, price=100.0, ticker="A"):
    return {"side": side, "ticker": ticker, "qty": qty, "price": price}


def test_normal_buy_is_allowed():
    assert check_order(order(), state(), L).ok


def test_oversized_order_rejected():
    d = check_order(order(qty=300), state(), L)          # Rs 30k > 25% of Rs 100k
    assert not d.ok and "large" in d.reason


def test_position_cap_rejected():
    s = state(cash=80_000.0, positions={"A": 200}, prices={"A": 100.0})
    d = check_order(order(qty=100), s, L)                # would hold Rs 30k > 25k
    assert not d.ok and "per-stock" in d.reason


def test_no_leverage():
    d = check_order(order(), state(cash=5_000.0), L)
    assert not d.ok and "cash" in d.reason


def test_no_shorting_but_selling_held_shares_is_fine():
    assert not check_order(order("sell", 10), state(), L).ok
    assert check_order(order("sell", 50), state(positions={"A": 50}), L).ok


def test_daily_loss_blocks_buys_but_not_sells():
    s = state(equity=97_000.0, cash=97_000.0, positions={"A": 50})
    assert not check_order(order("buy"), s, L).ok
    assert check_order(order("sell", 50), s, L).ok


def test_daily_order_cap():
    assert not check_order(order(), state(orders_today=30), L).ok


@pytest.mark.parametrize("qty", [0, -5, 1.5])
def test_bad_quantities_rejected(qty):
    assert not check_order(order(qty=qty), state(), L).ok


def test_kill_reasons():
    assert kill_reasons(state(equity=95_000.0), L) == []
    assert kill_reasons(state(equity=85_000.0), L)             # 15% drawdown
    assert kill_reasons(state(rejected_today=10), L)           # rejection storm