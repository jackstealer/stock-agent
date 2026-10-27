import json
import sys
import traceback
from pathlib import Path

import pandas as pd
import yaml

from ..backtest.costs import get_costs
from ..data.storage import read_bars
from ..monitor.alerts import send_alert
from ..risk import killswitch
from ..risk.limits import RiskLimits
from .broker import PaperBroker

SAFETY = 0.99          # keep a 1% cash buffer so fees never cause rejections
MOMENTUM_K = 5
REBALANCE_EVERY = 5    # in runs (trading days)


# ---- strategies: ctx -> {ticker: weight}, or None for "no change" -------------
def buy_hold(ctx):
    if ctx["positions"]:
        return None
    n = len(ctx["tickers"])
    return {t: 1 / n for t in ctx["tickers"]}


def momentum_top5(ctx):
    if ctx["runs_since_rebalance"] < REBALANCE_EVERY - 1:
        return None
    top = ctx["ret_20"].dropna().nlargest(MOMENTUM_K).index
    return {t: 1 / MOMENTUM_K for t in top}


ACCOUNTS = {
    "buy_hold": (buy_hold, RiskLimits(max_drawdown_pct=0.99)),
    "momentum_top5": (momentum_top5, RiskLimits()),
}


# ---- data ---------------------------------------------------------------------
def load_frames(tickers):
    """Open/close tables by ISO date, cut at the latest day EVERY ticker has."""
    opens, closes, last = {}, {}, {}
    for t in tickers:
        d = read_bars(t, "1d").sort_values("timestamp")
        day = d["timestamp"].dt.strftime("%Y-%m-%d")
        opens[t] = pd.Series(d["open"].to_numpy(), index=day.to_numpy())
        closes[t] = pd.Series(d["close"].to_numpy(), index=day.to_numpy())
        last[t] = day.iloc[-1]
    latest = min(last.values())
    O = pd.DataFrame(opens).sort_index().loc[:latest]
    C = pd.DataFrame(closes).sort_index().loc[:latest]
    lagging = [t for t, v in last.items() if v < max(last.values())]
    return O, C, latest, lagging


# ---- trading ------------------------------------------------------------------
def rebalance(broker, day, targets, opens):
    """Sell names that left the target, buy names that entered it. Names that
    stay are left alone (same rule as the backtester, which limits turnover)."""
    filled = rejected = 0
    equity = broker.equity()
    slip = broker.costs["slippage_pct"] / 100

    for t, qty in dict(broker.s["positions"]).items():
        if t not in targets:
            r = broker.submit(day, t, "sell", qty, float(opens[t]))
            filled += int(r["status"] == "filled")
            rejected += int(r["status"] == "rejected")

    for t, w in targets.items():
        if broker.s["positions"].get(t, 0) == 0:
            px = float(opens[t])
            budget = min(w * equity * SAFETY, broker.s["cash"])
            qty = int(budget // (px * (1 + slip)))
            if qty > 0:
                r = broker.submit(day, t, "buy", qty, px)
                filled += int(r["status"] == "filled")
                rejected += int(r["status"] == "rejected")
    return filled, rejected


def run_account(name, O, C, latest, cfg, alert) -> str:
    strategy, limits = ACCOUNTS[name]
    d = Path("state") / f"paper_{name}"
    d.mkdir(parents=True, exist_ok=True)
    rf = d / "runner.json"
    capital = float(cfg.get("capital_per_ticker", 100_000)) * len(cfg["tickers"])
    rs = (json.loads(rf.read_text(encoding="utf-8")) if rf.exists() else
          {"initial": capital, "last_run_day": None, "pending": None,
           "runs_since_rebalance": 999})
    if rs["last_run_day"] == latest:
        return f"{name}: already ran for {latest}"

    broker = PaperBroker(state_dir=d, capital=capital, costs=get_costs(cfg),
                         limits=limits, kill_path=d / "KILL.json", alert=alert)
    halted = killswitch.is_engaged() or killswitch.is_engaged(broker.kill_path)
    filled = rejected = 0
    note = ""

    # 1. Fill yesterday's signal at today's open (only if it is the very next bar)
    pending = rs["pending"]
    if pending:
        later = [x for x in O.index if x > pending["signal_day"]]
        if later and later[0] != latest:
            note = " (missed a trading day: pending orders expired)"
        elif later and not halted:
            broker.mark(latest, O.loc[latest].to_dict())
            filled, rejected = rebalance(broker, latest, pending["targets"],
                                         O.loc[latest])

    # 2. Mark to the close
    broker.mark(latest, C.loc[latest].to_dict())
    halted = halted or killswitch.is_engaged(broker.kill_path)

    # 3. Decide tomorrow's orders from today's close
    new_pending = None
    if not halted:
        ctx = {"tickers": list(O.columns), "positions": broker.s["positions"],
               "runs_since_rebalance": rs["runs_since_rebalance"],
               "ret_20": C.pct_change(20, fill_method=None).iloc[-1]}
        targets = strategy(ctx)
        if targets:
            new_pending = {"signal_day": latest, "targets": targets}
            rs["runs_since_rebalance"] = 0
        else:
            rs["runs_since_rebalance"] += 1

    rs.update(last_run_day=latest, pending=new_pending)
    rf.write_text(json.dumps(rs, indent=2), encoding="utf-8")

    eq = broker.equity()
    line = (f"{name}: Rs {eq:,.0f} ({eq / rs['initial'] - 1:+.2%}), "
            f"{len(broker.s['positions'])} holdings, "
            f"{filled} filled / {rejected} rejected{note}")
    return line + (" [HALTED]" if halted else "")


def run(config_path="configs/config.yaml") -> int:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    O, C, latest, lagging = load_frames(cfg["tickers"])
    if O.loc[latest].isna().any() or C.loc[latest].isna().any():
        raise ValueError(f"missing prices on {latest}")

    lines = [f"paper trading, data through {latest}"]
    if lagging:
        lines.append(f"note: {len(lagging)} stocks have newer bars than this run used")
    if killswitch.is_engaged():
        lines.append(f"GLOBAL KILL SWITCH ENGAGED: {killswitch.status()}")
    for name in ACCOUNTS:
        lines.append(run_account(name, O, C, latest, cfg, send_alert))
    send_alert("\n".join(lines))
    return 0


def main() -> None:
    try:
        code = run()
    except Exception:
        send_alert("paper trading CRASHED:\n" + traceback.format_exc()[-1500:])
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()