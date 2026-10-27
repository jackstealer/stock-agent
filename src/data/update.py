import sys
import traceback

import pandas as pd
import yaml

from ..monitor.alerts import send_alert
from ..monitor.quality import check_ticker
from .sources.eod import fetch_eod
from .storage import append_bars, read_bars

OVERLAP_DAYS = 7        # re-fetch a week we already have, to spot revisions
REVISION_TOL = 0.005    # a stored close changing by >0.5% means history was revised


def find_revisions(old: pd.DataFrame, new: pd.DataFrame, tol=REVISION_TOL) -> list:
    """Compare dates present in both stored and freshly fetched data."""
    if old.empty or new.empty:
        return []
    o = old.assign(d=old["timestamp"].dt.date)[["d", "close"]]
    n = new.assign(d=new["timestamp"].dt.date)[["d", "close"]]
    m = o.merge(n, on="d", suffixes=("_old", "_new"))
    diff = (m["close_new"] / m["close_old"] - 1).abs()
    return [(str(r.d), float(r.close_old), float(r.close_new))
            for r in m[diff > tol].itertuples()]


def update_ticker(ticker: str, root="data/raw", fetch=fetch_eod) -> dict:
    old = read_bars(ticker, "1d", root)
    if old.empty:
        raise ValueError("no stored history, run the backfill first")
    last = old["timestamp"].max()
    start = (last - pd.Timedelta(days=OVERLAP_DAYS)).strftime("%Y-%m-%d")
    new = fetch(ticker, start)

    revisions = find_revisions(old, new)
    if revisions:
        # A split or bonus rewrote past prices. Appending new rows on the new
        # price basis would create a fake jump, so we stop and ask for a re-backfill.
        return {"added": 0, "revisions": revisions}
    added = append_bars(new, root) if not new.empty else 0
    return {"added": added, "revisions": []}


def run(config_path="configs/config.yaml") -> int:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    total, problems = 0, []
    for t in cfg["tickers"]:
        try:
            r = update_ticker(t)
            total += r["added"]
            if r["revisions"]:
                d, a, b = r["revisions"][0]
                problems.append(f"{t}: history revised (split/bonus?), {d}: "
                                f"{a:.2f} -> {b:.2f}. New rows NOT added, re-run backfill")
            q = check_ticker(t)
            problems += [f"{t}: {p}" for p in q["problems"]
                         if p.startswith(("stale", "gap", "no data"))]
        except Exception as e:
            problems.append(f"{t}: FAILED - {e}")

    if problems:
        send_alert(f"stock-agent update: {len(problems)} problem(s)\n" + "\n".join(problems))
        return 1
    send_alert(f"stock-agent update OK: {total} new bars across {len(cfg['tickers'])} stocks")
    return 0


def main() -> None:
    try:
        code = run()
    except Exception:
        send_alert("stock-agent update CRASHED:\n" + traceback.format_exc()[-1500:])
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()