import json
from datetime import datetime, timezone
from pathlib import Path

from ..backtest.costs import DEFAULT_COSTS, trade_cost
from ..risk import killswitch
from ..risk.limits import RiskLimits, check_order, kill_reasons


class PaperBroker:
    """Simulated broker. Every order passes the risk gate. State survives restarts;
    every decision (filled or rejected) is appended to orders.jsonl."""

    def __init__(self, state_dir="state/paper", capital=2_500_000.0, costs=None,
                 limits=None, kill_path=killswitch.PATH, alert=None):
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.costs = costs or DEFAULT_COSTS
        self.limits = limits or RiskLimits()
        self.kill_path = Path(kill_path)
        self.alert = alert or (lambda msg: None)
        self.f = self.dir / "state.json"
        if self.f.exists():
            self.s = json.loads(self.f.read_text(encoding="utf-8"))
        else:
            self.s = {"cash": float(capital), "positions": {}, "prices": {},
                      "peak_equity": float(capital), "day": None,
                      "day_start_equity": float(capital),
                      "orders_today": 0, "rejected_today": 0}
            self._save()

    # ---- persistence -------------------------------------------------------
    def _save(self) -> None:
        tmp = self.f.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.s, indent=2), encoding="utf-8")
        tmp.replace(self.f)

    def _log(self, name: str, rec: dict) -> None:
        with open(self.dir / name, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    # ---- state -------------------------------------------------------------
    def equity(self) -> float:
        return self.s["cash"] + sum(q * self.s["prices"][t]
                                    for t, q in self.s["positions"].items())

    def _risk_state(self) -> dict:
        return {**self.s, "equity": self.equity()}

    def _check_kill(self) -> list:
        reasons = kill_reasons(self._risk_state(), self.limits)
        if reasons and killswitch.engage("; ".join(reasons), self.kill_path):
            self.alert("KILL SWITCH ENGAGED: " + "; ".join(reasons))
        return reasons

    # ---- daily operations --------------------------------------------------
    def mark(self, day: str, prices: dict) -> list:
        """Update prices, roll the day, track the peak, and trip the kill switch
        if limits are breached. Returns any kill reasons."""
        self.s["prices"].update({k: float(v) for k, v in prices.items()})
        missing = [t for t in self.s["positions"] if t not in self.s["prices"]]
        if missing:
            raise ValueError(f"no price for held positions: {missing}")
        eq = self.equity()
        if self.s["day"] != day:
            self.s.update(day=day, day_start_equity=eq,
                          orders_today=0, rejected_today=0)
        self.s["peak_equity"] = max(self.s["peak_equity"], eq)
        reasons = self._check_kill()
        self._log("equity.jsonl", {"day": day, "equity": eq, "cash": self.s["cash"],
                                   "positions": self.s["positions"]})
        self._save()
        return reasons

    def submit(self, day: str, ticker: str, side: str, qty: int,
               ref_price: float) -> dict:
        qty = int(qty)
        rec = {"time": datetime.now(timezone.utc).isoformat(), "day": day,
               "ticker": ticker, "side": side, "qty": qty, "ref_price": ref_price}
        if killswitch.is_engaged(self.kill_path):
            return self._reject(rec, "kill switch engaged")

        slip = self.costs["slippage_pct"] / 100
        px = ref_price * (1 + slip) if side == "buy" else ref_price * (1 - slip)
        decision = check_order({"side": side, "ticker": ticker, "qty": qty,
                                "price": px}, self._risk_state(), self.limits)
        if not decision.ok:
            return self._reject(rec, decision.reason)

        value = qty * px
        fee = trade_cost(value, side, self.costs)
        if side == "buy":
            if value + fee > self.s["cash"]:
                return self._reject(rec, "not enough cash including fees")
            self.s["cash"] -= value + fee
            self.s["positions"][ticker] = self.s["positions"].get(ticker, 0) + qty
        else:
            self.s["cash"] += value - fee
            left = self.s["positions"][ticker] - qty
            if left:
                self.s["positions"][ticker] = left
            else:
                del self.s["positions"][ticker]
        self.s["prices"].setdefault(ticker, float(ref_price))
        self.s["orders_today"] += 1
        rec.update(status="filled", fill_price=px, fee=fee)
        self._log("orders.jsonl", rec)
        self._save()
        return rec

    def _reject(self, rec: dict, reason: str) -> dict:
        self.s["rejected_today"] += 1
        rec.update(status="rejected", reason=reason)
        self._log("orders.jsonl", rec)
        self._check_kill()
        self._save()
        return rec