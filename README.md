# stock-agent

A research and paper-trading system for 25 large-cap NSE stocks, built around one idea: **evaluate honestly before trusting anything**. It has a cost-aware backtester, a locked test split, experiment tracking, risk limits with a kill switch, and a gate that decides whether a strategy has earned a further look.

> **Status: research project, paper trading only.** No real orders are ever sent to a broker. Nothing here is investment advice, and no strategy built so far has beaten a simple buy-and-hold benchmark (see Results).

## What is built

| Area | What it does |
|---|---|
| Data | Daily bars from yfinance for 25 stocks, validated and stored append-only as Parquet. Quality checks catch gaps, stale data, jumps and placeholder bars. A daily job fetches new bars, detects split/bonus revisions, and sends Telegram alerts. |
| Backtester | Signals at the close, fills at the next open, Indian delivery-trade charges plus slippage, long-only. The test split is locked in code and refuses to load. |
| Models | XGBoost with walk-forward training and purging of overlapping labels. Tests check that features use only past data. |
| Tracking | Every evaluation is logged to MLflow, and a trial registry counts every experiment. |
| Paper trading | A simulated broker with hard risk limits (position caps, no leverage, daily loss, drawdown) and a file-based kill switch. A daily runner keeps a buy-and-hold benchmark account and a momentum account. |
| News | A daily collector stores timestamped headlines per stock. The collection time is kept so future backtests can be point-in-time. No sentiment model is built yet. |
| Promotion gate | Deterministic code: the trial registry must match MLflow, enough data, deflated Sharpe on active returns (accounts for the number of trials tried), and a positive edge in both halves of the sample. |

## Results so far

Every experiment was pre-registered in `docs/experiments.md` (rules and pass/fail criteria written before running). All failed.

| Experiment | Window | Result | Verdict |
|---|---|---|---|
| 1. XGBoost, up more than 0.5% in 5 days | 2021-2023 walk-forward | AUC 0.48 / 0.48 / 0.51. Return -9.9%, Sharpe -0.57 vs buy-and-hold +75.8%, Sharpe 1.46. 3,534 trades, about Rs 6.4 lakh in costs on Rs 25 lakh | No edge; costs dominate |
| 2. Cross-sectional top-5, weekly | 2021-2023 | AUC 0.49 / 0.48 / 0.50. Sharpe 0.57 vs 1.46 buy-and-hold. Beat 8 of 20 random portfolios | Failed |
| 3a. 12-1 momentum, top 8 monthly | 2020-02 to 2023-12 | Sharpe 1.03 vs 1.10 benchmark. Beat 51 of 100 random portfolios. Costs 4.7% of capital | Failed |
| 3b. 200-day trend filter, weekly | 2020-02 to 2023-12 | Sharpe 1.46 vs 1.10. Max drawdown -17.1% vs -34.3%. But +0.86 in 2020-21 and -0.29 in 2022-23 | Failed the by-half check |

Reading: price-only daily signals on these stocks, at retail costs, did not beat the benchmark. The trend filter cut the 2020 crash drawdown but lagged in the calm years. Details and caveats are in `docs/experiments.md`.

## Safety

- Paper trading only. The broker is a simulation, and there is no order-sending code.
- Every simulated order passes a deterministic risk gate: no shorting, no leverage, position and order caps, a daily order cap, and a daily-loss block on new buys.
- The kill switch is a file. A drawdown breach or a storm of rejected orders engages it, and only a human command clears it.
- Risk limits and gate rules change only through reviewed pull requests, never at runtime.

## Limitations

- The 25 stocks are today's large caps, so survivorship bias flatters buy-and-hold.
- The evaluation windows are short and contain one crash and one strong recovery.
- yfinance is unofficial and can break; the daily job alerts when it does.
- The scheduler runs on a laptop (Windows Task Scheduler), so a day can be missed; the job catches up on the next run.
- Cost rates approximate Indian delivery charges and should be checked against a broker's current fee table.

## Not built yet

Live broker data (Angel One WebSocket), CI and containers, a dashboard, and an LLM sentiment feature (headlines are only being collected so far).

## Quick start (Windows PowerShell)

```powershell
git clone https://github.com/jackstealer/stock-agent.git
cd stock-agent
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env             # then fill in Telegram values (optional)
.venv\Scripts\python.exe -m src.data.backfill
.venv\Scripts\python.exe -m pytest -v
.venv\Scripts\python.exe -m src.backtest.baselines train
.venv\Scripts\python.exe -m src.paper.run_daily
```

## Layout

```
src/data/       sources, schema validation, append-only storage, backfill, daily update
src/monitor/    data quality checks, Telegram alerts
src/backtest/   costs, engine, portfolio engine, baselines, locked splits
src/models/     features, walk-forward, experiments, MLflow tracking
src/risk/       risk limits, kill switch
src/paper/      paper broker, daily runner
src/news/       headline collector
src/gate/       promotion gate and trial registry
docs/           experiments.md (pre-registered log), gate.md, trials.yaml
```