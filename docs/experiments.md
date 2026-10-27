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