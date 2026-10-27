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