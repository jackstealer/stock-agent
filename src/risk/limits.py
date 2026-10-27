from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    max_position_pct: float = 0.25        # one stock, as a share of equity
    max_order_value_pct: float = 0.25     # one order, as a share of equity
    max_gross_exposure_pct: float = 1.0   # 1.0 = no leverage
    max_orders_per_day: int = 30
    max_daily_loss_pct: float = 0.02      # past this, new buys are blocked
    max_drawdown_pct: float = 0.10        # past this, the kill switch engages
    max_rejections_per_day: int = 10      # a rejection storm means a runaway bug


@dataclass(frozen=True)
class Decision:
    ok: bool
    reason: str = ""


def load_limits(cfg: dict) -> RiskLimits:
    """Optional overrides from a `risk:` section in config.yaml."""
    return RiskLimits(**cfg.get("risk", {}))


def check_order(order: dict, state: dict, limits: RiskLimits) -> Decision:
    """order: side, ticker, qty, price. state: equity, cash, positions, prices,
    orders_today, day_start_equity. Pure function: same input, same answer."""
    side, ticker = order["side"], order["ticker"]
    qty, price = order["qty"], order["price"]
    equity = state["equity"]

    if side not in ("buy", "sell"):
        return Decision(False, f"bad side: {side}")
    if qty <= 0 or int(qty) != qty:
        return Decision(False, f"bad quantity: {qty}")
    if price <= 0 or equity <= 0:
        return Decision(False, "bad price or equity")
    if state["orders_today"] >= limits.max_orders_per_day:
        return Decision(False, f"daily order cap {limits.max_orders_per_day} reached")

    held = state["positions"].get(ticker, 0)
    if side == "sell":
        if qty > held:
            return Decision(False, f"sell {qty} > held {held}: no shorting")
        return Decision(True)

    value = qty * price
    if value > limits.max_order_value_pct * equity:
        return Decision(False, "order too large for equity")
    if value > state["cash"]:
        return Decision(False, "not enough cash: no leverage")
    if equity / state["day_start_equity"] - 1 <= -limits.max_daily_loss_pct:
        return Decision(False, "daily loss limit hit: no new buys")
    if (held + qty) * price > limits.max_position_pct * equity:
        return Decision(False, "position would exceed per-stock cap")
    gross = sum(q * state["prices"].get(t, price)
                for t, q in state["positions"].items()) + value
    if gross > limits.max_gross_exposure_pct * equity:
        return Decision(False, "gross exposure limit")
    return Decision(True)


def kill_reasons(state: dict, limits: RiskLimits) -> list:
    """Conditions severe enough to halt ALL trading until a human intervenes."""
    reasons = []
    peak = state["peak_equity"]
    if peak > 0:
        dd = state["equity"] / peak - 1
        if dd <= -limits.max_drawdown_pct:
            reasons.append(f"drawdown {dd:.1%} breached the "
                           f"-{limits.max_drawdown_pct:.0%} limit")
    if state["rejected_today"] >= limits.max_rejections_per_day:
        reasons.append(f"{state['rejected_today']} orders rejected today "
                       "(possible runaway loop)")
    return reasons