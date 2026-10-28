import json
from pathlib import Path

import pandas as pd


def read_jsonl(path) -> list:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def equity_curve(name: str, root="state") -> pd.Series:
    """Equity at the last mark of each day for one paper account."""
    rows = read_jsonl(Path(root) / f"paper_{name}" / "equity.jsonl")
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series({r["day"]: r["equity"] for r in rows})
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1


def account_summary(name: str, root="state") -> dict:
    d = Path(root) / f"paper_{name}"
    state_file = d / "state.json"
    if not state_file.exists():
        return {}
    s = json.loads(state_file.read_text(encoding="utf-8"))
    runner_file = d / "runner.json"
    runner = (json.loads(runner_file.read_text(encoding="utf-8"))
              if runner_file.exists() else {})
    eq = equity_curve(name, root)
    return {"cash": s["cash"], "positions": s["positions"],
            "holdings": len(s["positions"]),
            "equity": float(eq.iloc[-1]) if len(eq) else s["cash"],
            "initial": runner.get("initial"),
            "last_run_day": runner.get("last_run_day"),
            "orders_today": s["orders_today"], "rejected_today": s["rejected_today"],
            "killed": (d / "KILL.json").exists()}


def recent_orders(name: str, root="state", n: int = 20) -> pd.DataFrame:
    rows = read_jsonl(Path(root) / f"paper_{name}" / "orders.jsonl")
    cols = ["day", "ticker", "side", "qty", "status", "fill_price", "fee", "reason"]
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=cols)
    return df.reindex(columns=cols).tail(n).iloc[::-1].reset_index(drop=True)