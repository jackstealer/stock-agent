DEFAULT_COSTS = {
    "slippage_pct": 0.05,      # worse fill on every trade, in percent
    "brokerage_flat": 20.0,    # rupees per order; the lower of flat or pct applies
    "brokerage_pct": 0.1,
    "brokerage_min": 5.0,
    "stt_pct": 0.1,            # delivery: charged on both buy and sell
    "stamp_pct": 0.015,        # buy side only
    "exchange_pct": 0.00297,   # NSE transaction charge
    "sebi_pct": 0.0001,
    "gst_pct": 18.0,           # on brokerage + exchange + SEBI fees
}


def get_costs(cfg: dict) -> dict:
    """Defaults, overridden by the `costs:` section of config.yaml."""
    return {**DEFAULT_COSTS, **cfg.get("costs", {})}


def trade_cost(value: float, side: str, c: dict) -> float:
    """Total charges in rupees for one order of the given traded value."""
    brokerage = max(min(c["brokerage_flat"], value * c["brokerage_pct"] / 100),
                    c["brokerage_min"])
    exchange = value * c["exchange_pct"] / 100
    sebi = value * c["sebi_pct"] / 100
    gst = (brokerage + exchange + sebi) * c["gst_pct"] / 100
    stt = value * c["stt_pct"] / 100
    stamp = value * c["stamp_pct"] / 100 if side == "buy" else 0.0
    return brokerage + exchange + sebi + gst + stt + stamp