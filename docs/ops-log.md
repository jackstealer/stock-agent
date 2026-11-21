# Operations Log

Performance metrics captured during maintenance phases.

| date       | phase | metric                  | value          | command used                                    |
|------------|-------|-------------------------|----------------|-------------------------------------------------|
| 2026-10-31 | 0     | pytest_median_seconds   | 10.16          | Measure-Command pytest -q --durations=10        |
| 2026-10-31 | 0     | pytest_count            | 83             | pytest -q --durations=10                        |
| 2026-10-31 | 0     | quality_seconds         | 1.99           | Measure-Command python -m src.monitor.quality   |
| 2026-10-31 | 0     | quality_tickers_clean   | 25/25          | python -m src.monitor.quality                   |
| 2026-10-31 | 0     | gate_trials             | 4              | python -m src.gate.check                        |
| 2026-10-31 | 0     | gate_sharpe_hurdle      | 0.53           | python -m src.gate.check                        |
| 2026-10-31 | 0     | chain_duration_seconds  | 72.9,94.1,82.3 | logs\chain.log timestamps (3 complete runs)     |
| 2026-10-31 | 0     | scheduler_last_result   | 0              | schtasks /query /tn stock-agent-update          |
| 2026-10-31 | 0     | paper_buy_hold_equity   | 2553216.47     | python -c account_summary('buy_hold')           |
| 2026-10-31 | 0     | paper_momentum_equity   | 2597296.88     | python -c account_summary('momentum_top5')      |
| 2026-10-31 | 1     | pytest_cold_seconds     | 13.34          | Measure-Command pytest -q (Run 1 cold, pycache cleared) |
| 2026-10-31 | 1     | pytest_warm_run2_s      | 12.13          | Measure-Command pytest -q (Run 2 warm)          |
| 2026-10-31 | 1     | pytest_warm_run3_s      | 10.97          | Measure-Command pytest -q (Run 3 warm)          |
| 2026-10-31 | 1     | pytest_warm_median_s    | 12.13          | warm median of runs 2-3                         |
| 2026-10-31 | 1     | pytest_count            | 83             | pytest -q (confirmed)                           |
| 2026-10-31 | 1     | local_branch_deleted    | feat/risk-paper| git branch -D feat/risk-paper                   |
| 2026-10-31 | 1     | slowdown_31s_cause      | not_reproduced | cold/warm ratio 1.10x; threshold 2x not reached |

## Baseline reference (2026-10-27)

Train split baselines:
- buy_hold: +85.2% (Sharpe 0.91, max drawdown -34.3%, 25 trades)
- ma_20_100: +34.4% (Sharpe 0.77, 304 trades)
- random mean: +23.7%

Val split baselines:
- buy_hold: +25.8% (Sharpe 2.74)
- ma_20_100: +16.8% (Sharpe 2.51)
- random mean: +8.5%

## Notes

- Phase 0 baseline established 2026-10-31. All baselines match regression reference.
- Chain log shows one incomplete run (2026-10-30 16:19:12.08) with no exit lines.
- ITC.NS has 1934 rows vs 1933 for other 24 tickers (extra date 2025-03-18, cause unknown).

## Phase 2: docs truthfulness (2026-11-21)

| Date | Phase | Metric | Value | How measured |
|---|---|---|---|---|
| 2026-11-21 | 2 | pytest_count | 99 | pytest -q on docs/case-study (83 + 16 docs tests) |
| 2026-11-21 | 2 | pytest_s | 18.54 | same run |
| 2026-11-21 | 2 | baselines_train_val | match | all reference numbers identical |
| 2026-11-21 | 2 | gate_check_main | exit 1 seen, then exit 0 | exit 1 came from an uncommitted exp4 line in trials.yaml, now removed |
| 2026-11-21 | 2 | itc_2025_03_18 | yfinance gap | NSE traded that day; yfinance has no bar for RELIANCE.NS, TCS.NS |

- An uncommitted Phase 2 attempt by another agent (sentiment scorer, Angel One feed,
  Exp 4 design, trials.yaml edit) is saved on local branch
  backup/agent-phase2-2026-11-21. It is not merged; see the PR description.
