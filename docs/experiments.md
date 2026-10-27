# Experiment log

Every experiment goes here, including failures. The evaluation window is
2021-2023 (walk-forward). The test split is untouched.

## Exp 1: XGBoost baseline, price-only features
- Setup: 10 technical features, label = up >0.5% over 5 days (next open to open+5),
  one shared model for 25 stocks, retrained yearly with purged training data,
  signal when prob > 0.5.
- Result: AUC 0.478 / 0.477 / 0.514 (2021 / 2022 / 2023). Net return -9.9%,
  Sharpe -0.57, 3,534 trades, Rs 6.4 lakh in costs. Buy-and-hold: +75.8%, Sharpe 1.46.
- Conclusion: no edge from price-only features. Overtrading costs dominate.
- Not changed after seeing results: threshold, features, params.
## Exp 2: Cross-sectional top-5 portfolio (design fixed before running)
- Label: does the stock's 5-day forward return (next open to open+5) beat the
  same-day median across the 25 stocks?
- Features: the same 10 features, converted to same-day cross-sectional percentile
  ranks (removes market-wide level, keeps relative position).
- Model: same XGBoost params, retrained yearly with purged training data (2021-2023).
- Portfolio: hold the top 5 by predicted probability, equal weight, rebalance every
  5 trading days. Names kept across a rebalance are not traded (limits turnover).
  Signal at the close, trade at the next open, same costs as before.
- Compared against: equal-weight buy-and-hold of all 25, a momentum rule
  (top 5 by 20-day return), and 20 random top-5 portfolios.
- Success requires ALL of: (1) Sharpe above buy-and-hold, or similar return with a much
  smaller drawdown; (2) Sharpe above the momentum rule; (3) Sharpe above all 20
  random portfolios.
- Anything less is a failure, and gets logged as one.
- Result: AUC 0.487 / 0.482 / 0.501. Model top-5: +25.9%, Sharpe 0.57, max drawdown
  -31.8%, 957 trades, Rs 6.5 lakh fees + Rs 2.8 lakh slippage. Buy-and-hold (25 stocks):
  +75.8%, Sharpe 1.46, drawdown -17.2%. Momentum top-5: -3.8%, Sharpe 0.01. Random
  top-5 (mean of 20): +24.6%, Sharpe 0.53; model beat 8 of 20.
- Verdict against pre-registered criteria: (1) FAIL, (2) pass, (3) FAIL. Experiment failed.
- Conclusion: no edge from price-only features in either formulation (absolute and
  cross-sectional). Costs from turnover are a large drag. Nothing was tuned afterwards.
  ## Exp 3: Two low-turnover rule-based strategies (design fixed before running)
No model is trained, so there are no fitted parameters. Every number below is fixed
now and is not tuned afterwards. This counts as 2 more trials (3a, 3b), so 4 evaluated
formulations in total so far.

- Window: 2020-02-03 to the validation end (2023-12-29) for every strategy and the
  benchmark. The test split is untouched. Includes the Mar-2020 crash and the 2021 bull
  run. One market regime sequence only, which is a stated limitation.
- Costs: the standard cost model (brokerage, STT, stamp duty, exchange fees, GST, 0.05%
  slippage). Signals at the close, fills at the next open.
- Benchmark: equal-weight buy-and-hold of all 25 stocks (Rs 1 lakh each).

3a, Momentum, monthly. Score = close[t-21] / close[t-252] - 1 (12-1 month momentum).
Every 21 trading days hold the top 8 of 25, equal weight. Names that stay are not traded.
Compared with 100 random top-8 portfolios using the same cadence.
  Pass requires ALL of:
  (1) net Sharpe above the benchmark's
  (2) net Sharpe above at least 95 of the 100 random portfolios
  (3) fees + slippage below 3% of starting capital over the window
  (4) Sharpe difference vs benchmark positive in BOTH halves (2020-02 to 2021-12,
      2022-01 to 2023-12)

3b, Trend filter on the benchmark. Equal-weight index = mean of each stock's close divided
by its first close. On the last trading day of each week: hold all 25 if the index is above
its 200-day average, otherwise hold cash. Cash until the average exists.
  Pass requires ALL of:
  (1) net Sharpe at least the benchmark's
  (2) max drawdown at most 70% of the benchmark's (30% smaller or better)
  (3) fees + slippage below 3% of starting capital over the window
  (4) Sharpe not worse than the benchmark's by more than 0.15 in EITHER half

Interpretation, fixed in advance: passing is weak evidence (one window, today's large caps
only, survivorship bias). A pass makes a strategy a candidate for the paper-trading
account and one single look at the locked test split. It is not a conclusion. Any
failure is logged as a failure. No re-runs to tune anything. If a bug is found, the fix and
re-run are logged as the same experiment with the bug disclosed.

Prior (a guess, written before running): 3b probably cuts drawdown through Mar-2020 but
may lag in the calm bull years; 3a probably fails criterion (2) or (4).
- Result (window 2020-02-03 to 2023-12-29, 969 days, 25 stocks, net of costs):
  Benchmark equal-weight buy-and-hold: +106.6%, Sharpe 1.10, max drawdown -34.3%.
  3a momentum 12-1 top-8 monthly: +107.7%, Sharpe 1.03, drawdown -32.7%, 172 trades,
  costs 4.7% of capital. Random top-8 (mean of 100): +104.9%, Sharpe 1.00.
  3b trend filter (200d): +101.5%, Sharpe 1.46, drawdown -17.1%, 225 trades, costs 2.2%.
- Verdicts against the pre-registered criteria:
  3a FAILED (all four failed: Sharpe below benchmark, beat 51/100 random, costs 4.7%,
  half-diffs -0.24 / +0.21).
  3b FAILED (passed Sharpe, drawdown and cost criteria; failed the by-half check:
  +0.86 in 2020-21, -0.29 in 2022-23).
- Observations: 3b's protection comes from the Mar-2020 crash and it lagged in the calm
  years, as predicted in the prior. 3a was indistinguishable from random picks and too
  expensive. Nothing was tuned afterwards. 3b is not promoted to a paper account under
  the pre-registered rule.
- Trials counted so far: 4 formulations evaluated (Exp 1, Exp 2, 3a, 3b), all failed.