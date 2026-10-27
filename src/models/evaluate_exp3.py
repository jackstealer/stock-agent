import numpy as np
import pandas as pd
import yaml

from ..backtest.costs import get_costs
from ..backtest.engine import compute_metrics, run_backtest
from ..backtest.portfolio import run_portfolio
from ..data.schema import TZ
from ..data.storage import read_bars
from .tracking import log_run

START = "2020-02-03"
TOP_K = 8
REBALANCE_EVERY = 21          # trading days
MOM_LONG, MOM_SKIP = 252, 21
SMA_DAYS = 200
N_RANDOM = 100
HALVES = ((None, "2021-12-31"), ("2022-01-01", None))


def momentum_score(C: pd.DataFrame) -> pd.DataFrame:
    """12-1 month momentum: uses only closes at least 21 trading days old."""
    return C.shift(MOM_SKIP) / C.shift(MOM_LONG) - 1


def trend_signal(C: pd.DataFrame) -> pd.Series:
    """1.0 = hold all stocks, 0.0 = cash. Decided at the close of the last trading
    day of each week from the equal-weight index vs its 200-day average, then held
    until the next decision. Cash until the average exists."""
    index = (C / C.iloc[0]).mean(axis=1)
    sma = index.rolling(SMA_DAYS).mean()
    raw = (index > sma).astype(float).where(sma.notna())
    iso = C.index.isocalendar()
    week = iso["year"].astype(str) + "-" + iso["week"].astype(str)
    last_of_week = (week != week.shift(-1)).to_numpy()
    return raw.where(last_of_week).ffill().fillna(0.0)


def load_all(tickers):
    opens, closes = {}, {}
    for t in tickers:
        d = read_bars(t, "1d").sort_values("timestamp").set_index("timestamp")
        opens[t], closes[t] = d["open"], d["close"]
    O, C = pd.DataFrame(opens), pd.DataFrame(closes)
    ok = O.notna().all(axis=1) & C.notna().all(axis=1)
    return O[ok], C[ok]


def combine(results: list) -> dict:
    return {"equity": pd.concat([r["equity"] for r in results], axis=1).sum(axis=1),
            "trades": sum(r["trades"] for r in results),
            "fees": sum(r["fees"] for r in results),
            "slippage": sum(r["slippage"] for r in results)}


def per_ticker(Wo, Wc, signal, costs, cap_t) -> dict:
    out = []
    for t in Wo.columns:
        d = pd.DataFrame({"timestamp": Wo.index, "open": Wo[t].to_numpy(),
                          "close": Wc[t].to_numpy()})
        out.append(run_backtest(d, signal, costs, cap_t))
    return combine(out)


def summarize(r: dict) -> dict:
    m = compute_metrics(r["equity"])
    m.update(trades=r["trades"], fees=r["fees"], slippage=r["slippage"])
    return m


def half_sharpe_diffs(r: dict, bench: dict) -> list:
    out = []
    for a, b in HALVES:
        out.append(compute_metrics(r["equity"].loc[a:b])["sharpe"]
                   - compute_metrics(bench["equity"].loc[a:b])["sharpe"])
    return out


def fmt(table: pd.DataFrame) -> pd.DataFrame:
    s = table.copy()
    for c in ["total_return", "cagr", "max_drawdown"]:
        s[c] = (s[c] * 100).map("{:.1f}%".format)
    s["sharpe"] = s["sharpe"].map("{:.2f}".format)
    for c in ["trades", "fees", "slippage"]:
        s[c] = s[c].map("{:,.0f}".format)
    return s


def verdict(name: str, checks: list) -> bool:
    print(f"\n{name}")
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    passed = all(ok for _, ok in checks)
    print("  => PASSED all pre-registered criteria" if passed else "  => FAILED")
    return passed


def main(config_path: str = "configs/config.yaml") -> None:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    costs, tickers = get_costs(cfg), cfg["tickers"]
    cap_t = float(cfg.get("capital_per_ticker", 100_000))
    capital = cap_t * len(tickers)
    start = pd.Timestamp(START, tz=TZ)
    end = pd.Timestamp(cfg["splits"]["val_end"], tz=TZ)      # test split never touched

    O, C = load_all(tickers)
    mom, sig = momentum_score(C), trend_signal(C)
    m = (O.index >= start) & (O.index <= end)
    Wo, Wc = O[m], C[m]
    print(f"Window: {Wo.index[0].date()} to {Wo.index[-1].date()} "
          f"({len(Wo)} trading days, {len(tickers)} stocks)")

    bench = per_ticker(Wo, Wc, np.ones(len(Wo)), costs, cap_t)
    r3a = run_portfolio(Wo, Wc, mom[m], costs, capital, TOP_K, REBALANCE_EVERY)
    r3b = per_ticker(Wo, Wc, sig[m].to_numpy(), costs, cap_t)

    rand = []
    for seed in range(N_RANDOM):
        rs = pd.DataFrame(np.random.default_rng(seed).random(Wo.shape),
                          index=Wo.index, columns=Wo.columns)
        rand.append(summarize(run_portfolio(Wo, Wc, rs, costs, capital,
                                            TOP_K, REBALANCE_EVERY)))
    rand_df = pd.DataFrame(rand)

    rows = {"benchmark_buy_hold_25": summarize(bench),
            "3a_momentum_12_1_top8": summarize(r3a),
            "3b_trend_filter_200d": summarize(r3b),
            f"random_top8 (mean of {N_RANDOM})": rand_df.mean().to_dict()}
    table = pd.DataFrame(rows).T
    print("\nNet of costs\n")
    print(fmt(table).to_string())

    b, a, t = rows["benchmark_buy_hold_25"], rows["3a_momentum_12_1_top8"], \
        rows["3b_trend_filter_200d"]
    cost_pct = lambda r: (r["fees"] + r["slippage"]) / capital
    beats = int((rand_df["sharpe"] < a["sharpe"]).sum())
    d_a, d_b = half_sharpe_diffs(r3a, bench), half_sharpe_diffs(r3b, bench)

    pass_a = verdict("3a Momentum", [
        (f"Sharpe {a['sharpe']:.2f} above benchmark {b['sharpe']:.2f}",
         a["sharpe"] > b["sharpe"]),
        (f"beats {beats} of {N_RANDOM} random portfolios (need 95)", beats >= 95),
        (f"costs {cost_pct(a):.1%} of capital (need < 3%)", cost_pct(a) < 0.03),
        (f"Sharpe diff by half {d_a[0]:+.2f} / {d_a[1]:+.2f} (both > 0)",
         d_a[0] > 0 and d_a[1] > 0)])
    pass_b = verdict("3b Trend filter", [
        (f"Sharpe {t['sharpe']:.2f} at least benchmark {b['sharpe']:.2f}",
         t["sharpe"] >= b["sharpe"]),
        (f"max drawdown {t['max_drawdown']:.1%} vs benchmark {b['max_drawdown']:.1%} "
         "(need <= 70% of it)",
         abs(t["max_drawdown"]) <= 0.7 * abs(b["max_drawdown"])),
        (f"costs {cost_pct(t):.1%} of capital (need < 3%)", cost_pct(t) < 0.03),
        (f"Sharpe diff by half {d_b[0]:+.2f} / {d_b[1]:+.2f} (both > -0.15)",
         d_b[0] > -0.15 and d_b[1] > -0.15)])

    base = {"window_start": START, "window_end": str(end.date()), "n_stocks": len(tickers)}
    log_run("exp3a_momentum_12_1_top8",
            {**base, "experiment": "3a", "top_k": TOP_K, "rebalance_every": REBALANCE_EVERY,
             "passed": pass_a},
            {}, table.loc[["benchmark_buy_hold_25", "3a_momentum_12_1_top8"]])
    log_run("exp3b_trend_filter_200d",
            {**base, "experiment": "3b", "sma_days": SMA_DAYS, "passed": pass_b},
            {}, table.loc[["benchmark_buy_hold_25", "3b_trend_filter_200d"]])


if __name__ == "__main__":
    main()