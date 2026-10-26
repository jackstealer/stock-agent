import sys

import yaml

from src.data.storage import read_bars

date = sys.argv[1]
with open("configs/config.yaml", encoding="utf-8") as f:
    tickers = yaml.safe_load(f)["tickers"]

for t in tickers:
    d = read_bars(t, "1d").sort_values("timestamp").reset_index(drop=True)
    d["ret"] = d["close"].pct_change()
    row = d[d["timestamp"].dt.strftime("%Y-%m-%d") == date]
    if not row.empty:
        print(f"{t:<14} {row['ret'].iloc[0]:+.1%}")