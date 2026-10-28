import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .registry import compare, load_trials, mlflow_run_names
from .stats import deflated_sharpe, expected_max_sharpe

# Gate constants. Changed only through a PR (see docs/gate.md), never at runtime.
MIN_DAYS = 500
DSR_MIN = 0.95
VAR_FLOOR_DAILY = (0.5 / np.sqrt(252)) ** 2     # between-trial Sharpe std: 0.5 per year


def paper_returns(name: str, root="state") -> pd.Series:
    """Daily returns of a paper account (last equity mark of each day)."""
    p = Path(root) / f"paper_{name}" / "equity.jsonl"
    rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    equity = pd.Series({r["day"]: r["equity"] for r in rows})
    return equity.pct_change().dropna()


def csv_returns(path: str):
    """CSV with a date index and columns strategy_ret, benchmark_ret (daily, net)."""
    df = pd.read_csv(path, index_col=0)
    return df["strategy_ret"], df["benchmark_ret"]


def evaluate(strat: pd.Series, bench: pd.Series, n_trials: int,
             registry_problems: list) -> list:
    """Returns (label, passed) for each gate rule. Pure function: easy to test."""
    df = pd.concat([strat, bench], axis=1, keys=["s", "b"]).dropna()
    active = df["s"] - df["b"]
    T = len(df)
    hurdle = expected_max_sharpe(n_trials, VAR_FLOOR_DAILY)
    dsr = deflated_sharpe(active, n_trials, VAR_FLOOR_DAILY) if T > 2 else 0.0
    half = T // 2
    m1 = active.iloc[:half].mean() if half else 0.0
    m2 = active.iloc[half:].mean() if T else 0.0
    return [
        ("trial registry matches MLflow"
         + (": " + "; ".join(registry_problems) if registry_problems else ""),
         not registry_problems),
        (f"{T} days of data (need >= {MIN_DAYS})", T >= MIN_DAYS),
        (f"deflated Sharpe of active returns {dsr:.2f} (need >= {DSR_MIN}); "
         f"{n_trials} trials, luck hurdle {hurdle * np.sqrt(252):.2f} annualised",
         dsr >= DSR_MIN),
        (f"mean active return positive in both halves "
         f"({m1 * 252:+.1%} / {m2 * 252:+.1%} annualised)", m1 > 0 and m2 > 0),
    ]


def main(argv) -> int:
    registered = [t["mlflow_run"] for t in load_trials()]
    problems = compare(registered, mlflow_run_names())
    n = len(registered)
    print(f"Trials registered: {n}")
    print(f"Luck hurdle for {n} trials: annualised Sharpe "
          f"{expected_max_sharpe(n, VAR_FLOOR_DAILY) * np.sqrt(252):.2f}")
    for p in problems:
        print(f"PROBLEM: {p}")
    if len(argv) < 2:
        return 1 if problems else 0

    if argv[1].endswith(".csv"):
        strat, bench = csv_returns(argv[1])
        name = argv[1]
    else:
        strat, bench = paper_returns(argv[1]), paper_returns(argv[2])
        name = f"{argv[1]} vs {argv[2]}"
    print(f"\nGate check: {name}")
    checks = evaluate(strat, bench, n, problems)
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    passed = all(ok for _, ok in checks)
    print("=> PASSED: one look at the locked test split is allowed (log it)." if passed
          else "=> NOT PROMOTED")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))