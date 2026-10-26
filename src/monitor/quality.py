import sys
from collections import Counter

import pandas as pd
import yaml

from ..data.schema import TZ
from ..data.storage import read_bars


def check_ticker(ticker, interval="1d", root="data/raw", today=None,
                 max_gap_days=5, jump_pct=0.20, stale_days=4) -> dict:
    """Scan one ticker's stored bars. Returns a dict with a list of problems."""
    df = read_bars(ticker, interval, root)
    if df.empty:
        return {"ticker": ticker, "rows": 0, "first": None, "last": None,
                "problems": ["no data"], "jumps": {}, "zero_vol_dates": set()}

    df = df.sort_values("timestamp").reset_index(drop=True)
    ts = df["timestamp"]
    today = today if today is not None else pd.Timestamp.now(tz=TZ)
    problems = []

    # 1. Stale: last bar is too old (stale_days allows weekends + a holiday)
    age = (today.normalize() - ts.iloc[-1].normalize()).days
    if age > stale_days:
        problems.append(f"stale: last bar is {age} days old")

    # 2. Gaps: long stretches with no bars
    gap_days = ts.diff().dt.days
    for i in gap_days[gap_days > max_gap_days].index:
        problems.append(f"gap: {int(gap_days[i])} days before {ts[i].date()}")

    # 3. Jumps: big one-day moves (real events, splits, or bad data)
    ret = df["close"].pct_change().abs()
    jumps = {ts[i].date(): float(ret[i]) for i in ret[ret > jump_pct].index}
    for d, pct in jumps.items():
        problems.append(f"jump: {pct:.0%} move on {d}")

    # 4. Zero-volume days
    zero_dates = set(ts[df["volume"] == 0].dt.date)
    if zero_dates:
        problems.append(f"zero volume on {len(zero_dates)} days")

    return {"ticker": ticker, "rows": len(df), "first": ts.iloc[0].date(),
            "last": ts.iloc[-1].date(), "problems": problems,
            "jumps": jumps, "zero_vol_dates": zero_dates}


def main(config_path="configs/config.yaml") -> None:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    reviewed = {str(d) for d in cfg.get("reviewed_jumps", [])}
    results = [check_ticker(t) for t in cfg["tickers"]]
    n = len(results)

    # Zero volume on the same date for >=80% of tickers = exchange-wide event
    zero_counts = Counter(d for r in results for d in r["zero_vol_dates"])
    market_zero = {d for d, c in zero_counts.items() if c >= 0.8 * n}

    for r in results:
        r["problems"] = [p for p in r["problems"]
                         if not p.startswith(("jump", "zero volume"))]
        odd_zero = r["zero_vol_dates"] - market_zero
        if odd_zero:
            r["problems"].append("zero volume (this stock only) on "
                                 + ", ".join(sorted(str(d) for d in odd_zero)))
        for d, pct in r["jumps"].items():
            if str(d) not in reviewed:
                r["problems"].append(f"jump: {pct:.0%} move on {d} (not reviewed)")

    # Row counts should be nearly equal across stocks
    counts = pd.Series({r["ticker"]: r["rows"] for r in results})
    median = counts.median()
    for r in results:
        if r["rows"] and abs(r["rows"] - median) > 0.02 * median:
            r["problems"].append(
                f"row count {r['rows']} differs from median {int(median)}")

    if market_zero:
        print("Market-wide zero-volume days (not counted as errors):",
              ", ".join(sorted(str(d) for d in market_zero)), "\n")

    bad = 0
    for r in results:
        status = "OK " if not r["problems"] else "BAD"
        print(f"{status} {r['ticker']:<16} rows={r['rows']:<5} "
              f"{r['first']} -> {r['last']}")
        for p in r["problems"]:
            print(f"      - {p}")
        bad += bool(r["problems"])

    print(f"\n{n - bad}/{n} tickers clean")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()