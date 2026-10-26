import sys
import time

import yaml

from .sources.eod import fetch_eod
from .storage import append_bars


def main(config_path: str = "configs/config.yaml") -> None:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    start = cfg.get("backfill_start", "2019-01-01")
    failed = []

    for ticker in cfg["tickers"]:
        try:
            df = fetch_eod(ticker, start)
            if df.empty:
                raise ValueError("no data returned")
            added = append_bars(df)
            print(f"{ticker}: fetched {len(df)}, added {added}")
        except Exception as e:
            failed.append(ticker)
            print(f"{ticker}: FAILED - {e}")
        time.sleep(1)          # be polite to the data source

    if failed:
        print(f"\nFailed tickers: {failed}")
        sys.exit(1)
    print("\nBackfill complete.")


if __name__ == "__main__":
    main()