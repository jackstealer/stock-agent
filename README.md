# stock-agent
![CI](https://github.com/jackstealer/stock-agent/actions/workflows/ci.yml/badge.svg)

A research and paper-trading system for 25 large-cap NSE stocks, built around one idea:
**evaluate honestly before trusting anything**. It has a daily data pipeline, a cost-aware
backtester, a locked test split, experiment tracking, a simulated broker with risk limits and
a kill switch, and a promotion gate that decides whether a strategy has earned a further look.

> **Status: research project, paper trading only.** No real orders are ever sent to a broker,
> and there is no code that could send one. Nothing here is investment advice. No strategy
> built so far has beaten a simple buy-and-hold of the same 25 stocks (see Results).

Full write-up: [docs/CASE_STUDY.md](docs/CASE_STUDY.md).

## Contents

1. What it does every day
2. What is built
3. Results so far
4. How a strategy is judged
5. Safety and risk limits
6. Setup
7. Configuration
8. Daily operation
9. Command reference
10. Where the data lives
11. Tests, CI and the pre-push hook
12. Working on this repository
13. Limitations
14. Not built yet
15. Layout

## 1. What it does every day

A Windows scheduled task runs [scripts/run_update.bat](scripts/run_update.bat) on weekdays at
18:30 IST. Each step appends its exit code, with a timestamp, to `logs\chain.log`.

1. **News**: collect the last 2 days of Google News headlines for each stock (already-stored
   headlines are skipped). Both the published time
   and the time we collected it are stored; only the collected time is trusted in research.
2. **Sentiment**: score new headlines with an offline word-list scorer (Google Gemini is
   optional). No experiment uses these scores yet.
3. **Data update**: fetch new daily bars from yfinance. It re-fetches the last 7 days to
   catch split or bonus revisions, and refuses to append if past bars changed. A day's bar is
   included only after 18:00 IST, so an unfinished candle is never stored.
4. **Paper trading**: only if the update succeeded, run the two paper accounts. If the laptop
   missed days, they are replayed in order. Only dates on which all 25 stocks have a bar are
   used.

Problems are sent to Telegram when credentials are set (otherwise they are only printed).

## 2. What is built

| Area | What it does |
|---|---|
| Data | Daily bars from yfinance for 25 stocks, validated and stored append-only as Parquet. A daily job fetches new bars, detects split/bonus revisions, and sends Telegram alerts. |
| Data quality | Checks for stale data, gaps over 5 days, one-day moves over 20%, zero-volume days, uneven row counts, and dates that only some stocks have. |
| Backtester | Signals at the close, fills at the next open, Indian delivery-trade charges plus 0.05% slippage, long-only. Single-stock and top-k portfolio engines, random-portfolio baselines. The test split is locked in code and refuses to load. |
| Models | XGBoost with walk-forward training and purging of overlapping labels. Tests check that features use only past data. |
| Tracking | Every evaluation is logged to MLflow (`sqlite:///mlflow.db`), and a trial registry counts every experiment. |
| Paper trading | A simulated broker that sends every order through a risk check, and a file-based kill switch. Two accounts: `buy_hold` (benchmark) and `momentum_top5`. |
| News | A daily collector stores timestamped headlines per stock. Each night the headlines are scored by an offline word-list scorer (`src/news/sentiment.py`; Google Gemini optional). No experiment uses the scores yet. |
| Promotion gate | Deterministic code: the trial registry must match MLflow, at least 500 days of data, deflated Sharpe on active returns (accounts for the number of trials tried), and a positive edge in both halves of the sample. |
| Dashboard | A read-only Streamlit page with three tabs: paper trading, data health, experiments and gate. It has no controls. |
| CI and hook | GitHub Actions runs the tests, builds a Docker image, and guards rule files. A pre-push hook runs the same checks before anything reaches GitHub. |

## 3. Results so far

Experiments 2 and 3 were pre-registered: their design and pass/fail criteria were committed to
`docs/experiments.md` before the code that produced the result (checkable with
`git merge-base --is-ancestor`, see the audit note in that file). Experiment 1's entry was
written after its result. All four failed.

| Experiment | Window | Result | Verdict |
|---|---|---|---|
| 1. XGBoost, up more than 0.5% in 5 days | 2021-2023 walk-forward | AUC 0.478 / 0.477 / 0.514. Return -9.9%, Sharpe -0.57 vs buy-and-hold +75.8%, Sharpe 1.46. 3,534 trades, about Rs 6.4 lakh in costs on Rs 25 lakh | No edge; costs dominate |
| 2. Cross-sectional top-5, weekly | 2021-2023 | AUC 0.487 / 0.482 / 0.501. Sharpe 0.57 vs 1.46 buy-and-hold. Beat 8 of 20 random portfolios | Failed |
| 3a. 12-1 momentum, top 8 monthly | 2020-02 to 2023-12 | Sharpe 1.03 vs 1.10 benchmark. Beat 51 of 100 random portfolios. Costs 4.7% of capital | Failed |
| 3b. 200-day trend filter, weekly | 2020-02 to 2023-12 | Sharpe 1.46 vs 1.10. Max drawdown -17.1% vs -34.3%. But +0.86 in 2020-21 and -0.29 in 2022-23 | Failed the by-half check |

An AUC of 0.50 is what a coin flip scores. Reading: price-only daily signals on these stocks,
at retail costs, did not beat the benchmark. The trend filter cut the 2020 crash drawdown but
lagged in the calm years. Details and caveats are in [docs/experiments.md](docs/experiments.md).

Reference baselines (`python -m src.backtest.baselines`), used to detect changed data:

| Split | buy_hold | ma_20_100 | random (mean of 5) |
|---|---|---|---|
| train (to 2022-12-31) | +85.2%, Sharpe 0.91, max drawdown -34.3%, 25 trades | +34.4%, Sharpe 0.77, 304 trades | +23.7% |
| val (2023) | +25.8%, Sharpe 2.74 | +16.8%, Sharpe 2.51 | +8.5% |

If a rerun gives different numbers, the stored data changed: investigate, never adjust.

## 4. How a strategy is judged

- **Splits** ([configs/config.yaml](configs/config.yaml)): train to 2022-12-31, validation
  2023, test from 2024. The test split raises `PermissionError` unless code asks for it
  explicitly, and no reported result uses it.
- **Costs**: brokerage, STT, stamp duty, exchange and SEBI fees, GST, and 0.05% slippage on
  every simulated trade (`src/backtest/costs.py`).
- **Baselines**: every strategy is compared with equal-weight buy-and-hold and with random
  portfolios that trade on the same schedule.
- **Pre-registration**: the design and pass/fail criteria are committed before the code that
  produces the result, the experiment runs once, and failures are logged as failures.
- **Trial registry** ([docs/trials.yaml](docs/trials.yaml)): every MLflow run must be listed.
  More trials raise the "luck hurdle" (with 4 trials it is an annualised Sharpe of 0.53).
- **Promotion gate** ([docs/gate.md](docs/gate.md)): a strategy gets one look at the test
  split only if the registry matches MLflow, it has at least 500 daily observations, the
  deflated Sharpe ratio of its active returns is at least 0.95, and its mean active return is
  positive in both halves.

## 5. Safety and risk limits

- Paper trading only. The broker is a simulation, and there is no order-sending code.
- Every simulated order passes a deterministic risk check (`src/risk/limits.py`): no shorting
  and no leverage.
- The kill switch is a file (`state/KILL_SWITCH.json`). A drawdown breach or a storm of
  rejected orders engages it, and only a human command clears it.
- Risk limits and gate rules change only with a written reason (see section 12), never at
  runtime.

| Limit | Default | Effect |
|---|---|---|
| Position size | 25% of equity per stock | order rejected |
| Order size | 25% of equity per order | order rejected |
| Gross exposure | 100% of equity (no leverage) | order rejected |
| Orders per day | 30 | order rejected |
| Daily loss | 2% | new buys blocked for the day |
| Drawdown | 10% | kill switch engages |
| Rejections per day | 10 | kill switch engages |

The `buy_hold` benchmark account uses a 99% drawdown limit, so a market fall does not stop the
benchmark itself.

## 6. Setup

Requirements: Git, Python 3.13 (CI and the Docker image use 3.13), and an internet connection.
The commands below are for Windows PowerShell, which is how the project runs day to day.

```powershell
git clone https://github.com/jackstealer/stock-agent.git
cd stock-agent
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
git config core.hooksPath .githooks   # every push runs the tests and checks first
copy .env.example .env                # then fill in the values you want (all optional)
.venv\Scripts\python.exe -m src.data.backfill
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m src.backtest.baselines train
.venv\Scripts\python.exe -m src.paper.run_daily
```

The backfill downloads daily bars from 2019-01-01 for all 25 stocks (one request per stock,
one second apart). The baselines should match the table in section 3.

Dashboard (read-only, no controls):

```powershell
.venv\Scripts\streamlit.exe run dashboard\app.py
```

On Linux or macOS the Python commands are the same with `.venv/bin/python`; the scheduled
chain is a Windows batch file, so another scheduler would be needed there (not tested).

## 7. Configuration

**`configs/config.yaml`**

| Key | Meaning |
|---|---|
| `tickers` | the 25 NSE symbols (yfinance format, e.g. `RELIANCE.NS`) |
| `backfill_start` | first date downloaded by the backfill (`2019-01-01`) |
| `splits.train_end`, `splits.val_end` | `2022-12-31` and `2023-12-31`; everything later is the locked test split |
| `costs.slippage_pct` | slippage per trade side, in percent (`0.05`) |
| `reviewed_jumps` | dates whose large one-day moves were checked by hand (`2020-03-23`) |
| `news_names` | the search phrase used for each stock's headlines |
| `capital_per_ticker` | optional; not set, so the code default of Rs 1 lakh per stock applies (Rs 25 lakh per paper account) |

**`.env`** (copy from [.env.example](.env.example); never commit it)

| Variable | Needed for |
|---|---|
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Telegram alerts. Without them, alerts are only printed. |
| `GEMINI_API_KEY` | optional. Empty means the offline scorer; if set, every new headline is sent to Google's API. |
| `ANGEL_API_KEY`, `ANGEL_CLIENT_ID`, `ANGEL_PIN`, `ANGEL_TOTP_SECRET` | not used by any code yet (read-only market data is planned) |

## 8. Daily operation

Create the scheduled task once (adjust the path to your clone):

```powershell
schtasks /create /tn "stock-agent-update" /tr "C:\path\to\stock-agent\scripts\run_update.bat" /sc weekly /d MON,TUE,WED,THU,FRI /st 18:30
```

The batch file starts with `cd /d C:\Users\ATUL\Desktop\stock-agent`; change that line if your
clone lives elsewhere. "Wake the computer to run" and "run as soon as possible after a missed
start" are set in the Task Scheduler window (task properties), not by this command.

Check that it is running:

```powershell
Get-Content logs\chain.log -Tail 20
schtasks /query /tn "stock-agent-update" /v /fo list | Select-String "Last Run Time|Last Result|Next Run Time"
```

A healthy day in `logs\chain.log` has a `chain start` line followed by `news exit 0`,
`sentiment exit 0`, `update exit 0` and `paper exit 0`. Each step also writes its own log:
`logs\news.log`, `logs\sentiment.log`, `logs\update.log`, `logs\paper.log`.

- `news exit 1` usually means Google News rate-limited a few feeds; the next run fetches a
  2-day window, so nothing is lost.
- `update exit 1` stops the chain before paper trading; read `logs\update.log` (and the
  Telegram alert) before doing anything else.
- A missed day (laptop asleep or off) is caught up on the next run.

The scheduled task runs whatever is checked out in that folder, so keep it on `main`.

## 9. Command reference

Run every command from the repository root with `.venv\Scripts\python.exe -m ...`.

| Command | What it does | Writes |
|---|---|---|
| `src.data.backfill` | download history from `backfill_start`; adds only rows not already stored | `data/raw/` |
| `src.data.update` | fetch new bars with a 7-day overlap, check them, alert | `data/raw/` |
| `src.monitor.quality` | full data-quality report; exit 1 if any stock has a problem | nothing |
| `src.news.collect` | collect the last 2 days of headlines, skipping stored ones | `data/news/` |
| `src.news.sentiment [--month YYYY-MM]` | score unscored headlines (default: last and this month, UTC) | `data/sentiment/` |
| `src.paper.run_daily` | run both paper accounts, replaying missed days | `state/paper_*` |
| `src.backtest.baselines train` (or `val`) | reference baselines; no MLflow run | nothing |
| `src.gate.check` | registry vs MLflow check and luck hurdle | nothing |
| `src.gate.check momentum_top5 buy_hold` | gate check of a paper account against the benchmark (exit 1 = not promoted) | nothing |
| `src.risk.killswitch status` | show whether the kill switch is engaged | nothing |
| `scripts.day_returns 2020-03-23` | print each stock's close-to-close move on one date | nothing |

Do **not** run `src.models.evaluate`, `src.models.evaluate_xs` or `src.models.evaluate_exp3`
casually: each run logs an MLflow run, which counts as a trial for the gate. The kill switch's
`engage` and `clear` commands are for the owner only.

## 10. Where the data lives

All of this is git-ignored and append-only. Do not edit or delete it by hand.

| Path | Contents |
|---|---|
| `data/raw/1d/<TICKER>.parquet` | daily bars per stock. New rows are added; existing rows are never rewritten. Writes go to a temporary file first, so a crash never leaves a half-written file. |
| `data/news/YYYY-MM.jsonl` | headlines, one JSON object per line, by UTC month of collection |
| `data/sentiment/YYYY-MM.jsonl` | headline scores; each record says which scorer produced it |
| `state/paper_buy_hold/`, `state/paper_momentum_top5/` | paper account state and history |
| `state/KILL_SWITCH.json` | exists only while the kill switch is engaged |
| `mlflow.db` | MLflow tracking database (every logged run is a trial) |
| `logs/` | chain and per-step logs |

## 11. Tests, CI and the pre-push hook

`python -m pytest -q` runs the whole suite offline. Tests never send Telegram messages or
call paid APIs. Besides unit tests they check that features use only past data, that missed
paper days replay in order, and that the docs are ASCII-only, free of overclaims, and have
working links.

GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs on every push to
`main` and every pull request:

| Job | What it checks |
|---|---|
| `tests` | the full test suite on Python 3.13 |
| `docker` | the slim jobs image builds and the scheduled jobs import without research libraries |
| `protected-files` | rule files changed only with a written reason; `docs/experiments.md` only grows |

The pre-push hook ([.githooks/pre-push](.githooks/pre-push)) runs before anything reaches
GitHub, because the owner works on `main` directly and CI can only report after a push. It
refuses the push unless:

- only `main` is pushed, as a fast-forward (no force-push, no other branches or tags);
- the commit being pushed is the checked-out one, with no uncommitted changes and no
  untracked Python files;
- the full test suite passes;
- `docs/experiments.md` lost no text;
- any protected file change carries a `Rules-change-reason:` line.

Enable it once per clone with `git config core.hooksPath .githooks`. It takes about 15-20
seconds. `git push --no-verify` skips it; use that only in an emergency.

## 12. Working on this repository

- All work happens on `main`. There are no other branches.
- Before committing: `git branch --show-current` must print `main`, and `pytest` must pass.
- Add files by name (not `git add .`), and never commit `.env`, `data/`, `state/`, `logs/`,
  `mlflow.db` or `mlruns/`.
- **Protected files** need a line `Rules-change-reason: <why, 15+ characters>` in the commit
  message: `docs/gate.md`, `docs/trials.yaml`, `src/gate/check.py`, `src/gate/stats.py`,
  `src/risk/limits.py`, `src/risk/killswitch.py`, `src/backtest/splits.py`. The list lives in
  `scripts/check_protected.py`.
- **`docs/experiments.md` is append-only**: add new sections, never edit or remove lines.

Adding an experiment:

1. Commit the design and the pass/fail criteria to `docs/experiments.md` first, with a prior.
2. Commit the code, then run it once on the train and validation data only.
3. Add the trial to `docs/trials.yaml` (a protected file: give a reason).
4. Append the result, pass or fail, to `docs/experiments.md`. Nothing is tuned afterwards.

## 13. Limitations

- The 25 stocks are today's large caps, so survivorship bias flatters buy-and-hold.
- The evaluation windows are short and contain one crash and one strong recovery.
- yfinance is unofficial and can break; the daily job alerts when it does.
- yfinance has no 2025-03-18 bar for 24 of the 25 stocks, although NSE traded that day. The
  date is in the locked test period, so no reported result uses it.
- The scheduler runs on a laptop, so a day can be missed; the job catches up on the next run.
- Cost rates approximate Indian delivery charges and should be checked against a broker's
  current fee table.
- The promotion gate was built after experiments 1-3, so it counts them as trials
  retroactively rather than having gated them in advance.
- The gate assumes a between-trial Sharpe spread (annualised 0.5); it is not measured.

## 14. Not built yet

- Live market data from a broker API (Angel One, read-only). Placeholders exist in
  `.env.example`; no code uses them.
- A sentiment experiment. Headlines have been collected since late October 2026; an
  experiment needs months more data and a pre-registered design.
- A second data source to cross-check yfinance (for example the exchange's daily files).
- Running the jobs somewhere other than a laptop. The Docker image exists; it is not deployed.

## 15. Layout

```
src/data/        yfinance source, schema validation, append-only storage, backfill, daily update
src/monitor/     data quality checks, Telegram alerts, report helpers for the dashboard
src/backtest/    costs, single-stock and portfolio engines, baselines, locked splits
src/models/      features, walk-forward XGBoost, cross-sectional ranker, experiments, MLflow
src/risk/        risk limits, kill switch
src/paper/       paper broker, daily runner
src/news/        headline collector, sentiment scorer
src/gate/        promotion gate and trial registry
dashboard/       read-only Streamlit page
configs/         config.yaml
scripts/         run_update.bat (daily chain), check_append_only.py, check_protected.py,
                 day_returns.py
.githooks/       pre-push hook
.github/         CI workflow
tests/           pytest suite
docs/            experiments.md (append-only experiment log), gate.md, trials.yaml,
                 CASE_STUDY.md, ops-log.md
Dockerfile       slim image for the scheduled jobs (requirements-jobs.txt)
```

Nothing in this repository is investment advice.
