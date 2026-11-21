# Case study: stock-agent

A research and paper-trading system for 25 large-cap NSE stocks. Paper trading only:
there is no code that sends orders to a broker. Nothing here is investment advice.

Every number in this file is copied from [experiments.md](experiments.md), and every
rule from [gate.md](gate.md) or the code. If they disagree, those files are right.

## 1. The question

Can a simple systematic strategy beat equal-weight buy-and-hold of the same 25 stocks
after Indian retail costs, judged in a way that is hard to fool yourself with?

Answer so far: no. Four formulations were tried and all four failed.

## 2. Architecture

| Part | Code | What it does |
|---|---|---|
| Data | `src/data/` | yfinance daily bars, schema validation, append-only Parquet, backfill from 2019-01-01, daily update that re-fetches 7 days and blocks appends if past bars were revised |
| Monitoring | `src/monitor/` | Quality checks (stale data, gaps, moves over 20%, zero volume) and Telegram alerts |
| Backtest | `src/backtest/` | Signals at the close, fills at the next open, Indian delivery charges plus 0.05% slippage, single-stock and top-k portfolio engines, random-portfolio baselines |
| Models | `src/models/` | Features that use only past data, purged walk-forward XGBoost, MLflow tracking |
| Risk | `src/risk/` | Order and position limits, a file-based kill switch |
| Paper trading | `src/paper/` | Simulated broker, daily runner with a buy-and-hold and a momentum account, replay of missed days in order |
| News | `src/news/` | Daily headline collector that stores both the published time and the collected time |
| Gate | `src/gate/` | Promotion gate: trial registry, deflated Sharpe, by-half check |
| Dashboard | `dashboard/app.py` | Read-only Streamlit page, no controls |
| CI | `.github/workflows/ci.yml` | Tests, a Docker image smoke test, and a protected-files job |

A Windows scheduled task runs `scripts/run_update.bat` on weekdays at 18:30 IST:
news, then the data update, then (only if the update succeeded) the paper runner.

## 3. Evaluation rules

- **Splits** (`configs/config.yaml`): train to 2022-12-31, validation 2023, test from
  2024. `get_split` in `src/backtest/splits.py` raises `PermissionError` for the test
  split unless the caller passes `allow_test=True`. No result below uses the test split.
- **Costs**: every simulated trade pays brokerage, STT, stamp duty, exchange and SEBI
  fees, GST, and 0.05% slippage (`src/backtest/costs.py`).
- **Baselines**: each strategy is compared with equal-weight buy-and-hold and with random
  portfolios that trade on the same schedule.
- **Pre-registration**: for Experiments 2 and 3 the design and pass/fail criteria were
  committed before the code that produced the result. Experiment 1's entry was written
  after its result. The audit note in [experiments.md](experiments.md) lists the commits.
- **Promotion gate** ([gate.md](gate.md)): a strategy gets one look at the test split
  only if the trial registry matches MLflow, it has at least 500 daily observations, the
  deflated Sharpe ratio of its active returns is at least 0.95 given the number of
  registered trials, and its mean active return is positive in both halves.

## 4. Results

| Exp | What | Window | Result | Verdict |
|---|---|---|---|---|
| 1 | XGBoost, label "up more than 0.5% in 5 days" | 2021-2023 walk-forward | AUC 0.478 / 0.477 / 0.514. Net -9.9%, Sharpe -0.57, 3,534 trades, Rs 6.4 lakh costs. Buy-and-hold +75.8%, Sharpe 1.46 | Failed |
| 2 | Cross-sectional ranks, top-5, rebalance every 5 days | 2021-2023 | AUC 0.487 / 0.482 / 0.501. +25.9%, Sharpe 0.57, drawdown -31.8%, 957 trades. Buy-and-hold +75.8%, Sharpe 1.46. Beat 8 of 20 random portfolios | Failed criteria 1 and 3 |
| 3a | 12-1 momentum, top 8, monthly | 2020-02-03 to 2023-12-29 | +107.7%, Sharpe 1.03 vs benchmark 1.10, beat 51 of 100 random, costs 4.7% of capital, half-diffs -0.24 / +0.21 | Failed all four criteria |
| 3b | 200-day trend filter on the index, weekly | 2020-02-03 to 2023-12-29 | +101.5%, Sharpe 1.46 vs 1.10, drawdown -17.1% vs -34.3%, costs 2.2%. Sharpe difference +0.86 in 2020-21, -0.29 in 2022-23 | Failed the by-half check |

Reading: price-only daily signals on these stocks did not beat buy-and-hold at retail
costs. 3b's better Sharpe came from avoiding the March 2020 crash; it lagged in the
calmer years, as its pre-registered prior predicted. It was not tuned afterwards.

## 5. Limitations

- The 25 stocks are today's large caps, so survivorship bias flatters buy-and-hold.
- Each experiment covers one short window with one crash and one recovery.
- Experiment 1 was not pre-registered.
- The promotion gate was built after Experiments 1-3, so it counted them retroactively.
- The gate assumes a between-trial Sharpe spread (annualised 0.5); it is not measured.
- yfinance is unofficial. It has no 2025-03-18 bar for 24 of the 25 stocks although NSE
  traded that day. The date is in the locked test period, so no result above uses it.
- Cost rates approximate Indian delivery charges and should be checked against a
  broker's current fee table.
- The jobs run on a laptop scheduler, so days can be missed; the paper runner replays
  them in order on the next run.

## 6. What the repository shows (each line can be checked in the code)

- An append-only daily data pipeline for 25 NSE stocks with schema validation,
  revision detection and Telegram alerts (`src/data/`, `src/monitor/`).
- Leakage controls: purged walk-forward training, a test split that refuses to load
  (`src/backtest/splits.py`), and tests that features use only past data (`tests/`).
- Four strategy trials reported as failures against fixed criteria, with the
  pre-registration status of each checkable from git history (`docs/experiments.md`).
- A promotion gate that reconciles a trial registry with MLflow and applies the deflated
  Sharpe ratio (`src/gate/`, `docs/gate.md`, `docs/trials.yaml`).
- A paper broker that sends every order through a risk check, with a kill switch, plus
  CI that runs tests, builds a Docker image, and guards rule files (`src/paper/`,
  `src/risk/`, `.github/workflows/ci.yml`).
