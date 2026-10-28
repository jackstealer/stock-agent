<div align="center">

# 📈 Stock Agent

### _A Research-Grade Algorithmic Trading System_

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![MLflow](https://img.shields.io/badge/mlflow-tracking-0194E2?logo=mlflow)](https://mlflow.org/)
[![XGBoost](https://img.shields.io/badge/xgboost-machine%20learning-orange)](https://xgboost.ai/)
[![Tested](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)

_Building quantitative trading strategies with scientific rigor, honest evaluation, and production-grade safety._

[Features](#-features) • [Architecture](#-architecture) • [Research](#-research-log) • [Setup](#-setup) • [Usage](#-usage) • [Results](#-experiment-results)

</div>

---

## 🎯 Philosophy

This project embodies **research integrity in quantitative finance**:

- **Honest Evaluation**: Every strategy is evaluated net of realistic transaction costs with walk-forward validation and locked test sets
- **No Snooping**: Test data remains untouched until a strategy passes validation criteria
- **Pre-Registration**: Success criteria are defined _before_ experiments run
- **Log Everything**: All experiments—successes and failures—are documented with reproducible code
- **Safety First**: Multi-layered risk controls, kill switches, and paper trading before any live deployment

> _"In God we trust. All others must bring data."_ — W. Edwards Deming

---

## ✨ Features

### 📊 Data Pipeline

- **Automated EOD Data**: Daily price/volume updates for 25 NSE stocks via yfinance
- **Quality Monitoring**: Automated checks for staleness, gaps, jumps, and anomalies
- **Revision Detection**: Alerts when historical prices change (splits, bonuses)
- **Robust Storage**: Parquet-based data lake with schema validation via Pandera
- **News Integration**: Collects and stores market news for sentiment analysis

### 🧪 Backtesting Engine

- **Cost-Aware**: Models slippage, brokerage, STT, stamp duty, exchange fees, GST
- **Walk-Forward Validation**: Prevents look-ahead bias with purged training data
- **Multiple Strategies**:
  - Time-series (single-stock predictions)
  - Cross-sectional (relative value, top-N portfolios)
  - Rule-based baselines (momentum, trend-following)
- **Realistic Execution**: Signals at close, fills at next open with slippage
- **Turnover Control**: Cost-aware rebalancing with same-name persistence

### 🤖 Machine Learning

- **XGBoost Models**: Conservative parameters (depth=3, strong regularization)
- **Feature Engineering**: 10 technical indicators (momentum, volatility, RSI, SMAs)
- **Cross-Sectional Ranking**: Percentile-based features for relative predictions
- **MLflow Tracking**: All experiments logged with parameters, metrics, and artifacts
- **Anti-Overfitting**: Yearly retraining, minimal tuning, pre-registered architectures

### 🛡️ Risk Management

- **Kill Switch**: Automated trading halt on breach of risk limits
- **Position Limits**: Max position size, sector exposure, portfolio concentration
- **Drawdown Protection**: Automatic circuit breaker on peak-to-valley losses
- **Daily Trade Caps**: Limits on orders per day and rejected orders
- **Paper Trading**: Full broker simulation with state persistence and order logging

### 🔍 Monitoring & Alerts

- **Data Quality Dashboards**: Automated daily checks across all tickers
- **Telegram Alerts**: Real-time notifications for data issues, experiments, trades
- **Equity Tracking**: Daily snapshots of paper/live portfolio performance
- **Experiment Logs**: Human-readable markdown logs of every trial

---

## 🏗️ Architecture

```
stock-agent/
├── src/
│   ├── data/
│   │   ├── sources/        # EOD data fetchers (yfinance)
│   │   ├── schema.py       # Pandera validation schemas
│   │   ├── storage.py      # Parquet read/write utilities
│   │   ├── backfill.py     # Historical data initialization
│   │   └── update.py       # Daily data refresh with revision detection
│   ├── models/
│   │   ├── features.py     # Technical indicator computation
│   │   ├── walkforward.py  # Time-series cross-validation
│   │   ├── crosssection.py # Cross-sectional ranking models
│   │   ├── evaluate.py     # Backtest evaluation harness
│   │   └── tracking.py     # MLflow experiment logging
│   ├── backtest/
│   │   ├── engine.py       # Single-stock backtester
│   │   ├── portfolio.py    # Multi-stock portfolio backtester
│   │   ├── costs.py        # NSE transaction cost model
│   │   ├── strategies.py   # Signal generators
│   │   ├── baselines.py    # Benchmark strategies
│   │   └── splits.py       # Train/val/test partitioning
│   ├── paper/
│   │   ├── broker.py       # Simulated broker with risk gates
│   │   └── run_daily.py    # Daily paper trading executor
│   ├── risk/
│   │   ├── killswitch.py   # Emergency trading halt
│   │   └── limits.py       # Risk limit definitions & checks
│   ├── monitor/
│   │   ├── quality.py      # Data quality scanner
│   │   └── alerts.py       # Telegram notification system
│   └── news/
│       └── collect.py      # News headline scraper
├── tests/                  # Comprehensive test suite (13 modules)
├── configs/
│   └── config.yaml         # Tickers, splits, costs, news mappings
├── data/
│   ├── raw/1d/             # Daily OHLCV parquet files
│   ├── news/               # News headlines by month
│   └── processed/          # Feature-engineered datasets
├── docs/
│   └── experiments.md      # Complete experiment log
└── scripts/
    ├── day_returns.py      # Daily return analysis utilities
    └── run_update.bat      # Windows scheduled task wrapper
```

### Technology Stack

| Category       | Tools                                     |
| -------------- | ----------------------------------------- |
| **Data**       | pandas, numpy, pyarrow, yfinance, Pandera |
| **ML**         | XGBoost, scikit-learn, MLflow             |
| **Testing**    | pytest (13 test modules)                  |
| **Monitoring** | Telegram Bot API, custom quality checks   |
| **Config**     | PyYAML, python-dotenv                     |

---

## 🔬 Research Log

All experiments are pre-registered with success criteria defined before execution. No post-hoc tuning.

### Current Universe

- **25 NSE Large-Cap Stocks**: RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, BHARTIARTL, ITC, LT, KOTAKBANK, AXISBANK, HINDUNILVR, BAJFINANCE, MARUTI, SUNPHARMA, TITAN, ASIANPAINT, ULTRACEMCO, NESTLEIND, WIPRO, HCLTECH, NTPC, POWERGRID, ONGC, TATASTEEL
- **Evaluation Window**: 2021-2023 (walk-forward)
- **Locked Test Set**: 2024+ (unopened)
- **Benchmark**: Equal-weight buy-and-hold

### Experiment 1: XGBoost Time-Series Baseline

**Hypothesis**: Price-only technical features can predict 5-day forward returns

- **Setup**: 10 technical indicators, binary label (gain >0.5% over 5 days), shared model across 25 stocks, yearly retraining
- **Result**: AUC 0.478/0.477/0.514 (2021/22/23), Net Return **-9.9%**, Sharpe **-0.57**, 3,534 trades, ₹640k in costs
- **Benchmark**: Buy-and-hold +75.8%, Sharpe 1.46
- **Verdict**: ❌ **FAILED** — No predictive edge, overtrading destroyed capital

### Experiment 2: Cross-Sectional Top-5 Portfolio

**Hypothesis**: Relative ranking across stocks reveals alpha missed by absolute predictions

- **Setup**: Cross-sectional percentile features, binary label (beat same-day median), top-5 equal-weight portfolio, 5-day rebalance
- **Pre-Registered Success Criteria**:
  1. Sharpe above buy-and-hold
  2. Sharpe above momentum baseline
  3. Sharpe above all 20 random top-5 portfolios
- **Result**: AUC 0.487/0.482/0.501, +25.9%, Sharpe 0.57, -31.8% max drawdown, 957 trades, ₹930k costs
- **Benchmarks**:
  - Buy-and-hold: +75.8%, Sharpe 1.46, -17.2% drawdown
  - Momentum: -3.8%, Sharpe 0.01
  - Random portfolios: mean +24.6%, Sharpe 0.53 (beat 8 of 20)
- **Verdict**: ❌ **FAILED** criteria 1 & 3 — No edge over simple baselines

### Experiment 3a: Momentum (12-1 Month, Monthly Top-8)

**Hypothesis**: Established momentum anomaly should work on NSE large-caps

- **Setup**: Score = (close[t-21] / close[t-252] - 1), top 8 of 25, monthly rebalance (21 days)
- **Pre-Registered Success Criteria**:
  1. Net Sharpe > benchmark
  2. Net Sharpe > 95 of 100 random top-8 portfolios
  3. Costs < 3% of capital
  4. Positive Sharpe difference vs benchmark in BOTH halves (2020-21, 2022-23)
- **Result**: +107.7%, Sharpe 1.03, -32.7% drawdown, 172 trades, **4.7% costs** (₹117k)
- **Benchmarks**: Buy-and-hold +106.6%, Sharpe 1.10; Random mean +104.9%, Sharpe 1.00 (beat 51 of 100)
- **Verdict**: ❌ **FAILED** all four criteria — Indistinguishable from random, too expensive

### Experiment 3b: Trend Filter (200-Day MA, Weekly)

**Hypothesis**: Simple trend-following should reduce drawdowns while preserving upside

- **Setup**: Hold all 25 if equal-weight index > 200-day MA, else cash; rebalance weekly
- **Pre-Registered Success Criteria**:
  1. Net Sharpe ≥ benchmark
  2. Max drawdown ≤ 70% of benchmark's (30%+ reduction)
  3. Costs < 3% of capital
  4. Sharpe not worse than benchmark by >0.15 in EITHER half
- **Result**: +101.5%, Sharpe 1.46, **-17.1% drawdown**, 225 trades, 2.2% costs
- **Benchmark**: +106.6%, Sharpe 1.10, -34.3% drawdown
- **Half-by-Half**: +0.86 (2020-21), **-0.29** (2022-23) vs benchmark
- **Verdict**: ❌ **FAILED** criterion 4 — Protected in crash but lagged in calm years

### Summary: 4 Formulations, 0 Deployments

Every strategy tested has failed pre-registered criteria. The search continues.

_Full experiment details with code: [`docs/experiments.md`](docs/experiments.md)_

---

## 🚀 Setup

### Prerequisites

- Python 3.8+
- Windows (batch scripts) or adapt for Linux/macOS
- Telegram Bot (optional, for alerts)

### Installation

```powershell
# Clone the repository
git clone <your-repo-url>
cd stock-agent

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
copy .env.example .env
# Edit .env and add your Telegram bot credentials
```

### Configuration

Edit `configs/config.yaml` to customize:

- **Tickers**: Stock universe (default: 25 NSE large-caps)
- **Splits**: Train/validation/test date boundaries
- **Costs**: Slippage, brokerage, taxes (default: NSE equity delivery)
- **Reviewed Jumps**: Dates with legitimate price jumps (splits, bonuses)

### Initial Data Download

```powershell
# Backfill historical data from 2019-01-01
python -m src.data.backfill

# Verify data quality
python -m src.monitor.quality

# Set up daily updates (Windows Task Scheduler)
# Run scripts/run_update.bat at 6 PM IST daily
```

---

## 📖 Usage

### Data Operations

```powershell
# Daily data update (checks for revisions, appends new bars)
python -m src.data.update

# Quality check across all tickers
python -m src.monitor.quality

# Collect news headlines
python -m src.news.collect
```

### Running Experiments

```powershell
# Experiment 1: Time-series XGBoost
python -m src.models.evaluate

# Experiment 2: Cross-sectional portfolio
python -m src.models.evaluate_xs

# Experiment 3: Rule-based strategies
python -m src.models.evaluate_exp3
```

All experiments log to MLflow. View results:

```powershell
mlflow ui
# Navigate to http://localhost:5000
```

### Paper Trading

```powershell
# Check kill switch status
python -m src.risk.killswitch status

# Run daily paper trades (if strategy deployed)
python -m src.paper.run_daily

# Engage kill switch manually
python -m src.risk.killswitch engage "manual halt for review"

# Clear kill switch (requires confirmation)
python -m src.risk.killswitch clear
```

### Testing

```powershell
# Run full test suite
pytest

# Run specific test module
pytest tests/test_backtest.py

# Run with coverage
pytest --cov=src tests/
```

---

## 📊 Experiment Results

### Performance Summary (2021-2023)

| Strategy                  | Return  | Sharpe | Max DD | Trades | Costs | Status    |
| ------------------------- | ------- | ------ | ------ | ------ | ----- | --------- |
| **Buy & Hold**            | +75.8%  | 1.46   | -17.2% | 0      | ₹0    | Benchmark |
| Exp 1 (XGB Time-Series)   | -9.9%   | -0.57  | N/A    | 3,534  | ₹640k | ❌ Failed |
| Exp 2 (XGB Cross-Section) | +25.9%  | 0.57   | -31.8% | 957    | ₹930k | ❌ Failed |
| Exp 3a (Momentum 12-1)    | +107.7% | 1.03   | -32.7% | 172    | ₹117k | ❌ Failed |
| Exp 3b (Trend Filter)     | +101.5% | 1.46   | -17.1% | 225    | ₹55k  | ❌ Failed |

### Key Insights

1. **Price-Only Features Are Insufficient**: Both ML approaches (Exp 1 & 2) failed to beat simple baselines
2. **Transaction Costs Matter**: High-frequency strategies bled capital through costs
3. **Regime Dependency**: Trend-following excelled in 2020 crash but lagged 2022-23
4. **Pre-Registration Works**: Objective criteria prevented post-hoc rationalization of mediocre results

---

## 🛡️ Risk Controls

### Multi-Layer Protection

1. **Kill Switch**: Automated halt on risk limit breach
   - Max drawdown from peak equity
   - Daily loss limits
   - Excessive rejected orders

2. **Position Limits**:
   - Max position size per stock
   - Max daily trades
   - Sector concentration limits

3. **Paper Trading**: Mandatory simulation before live deployment
   - Full cost model
   - State persistence across restarts
   - Order logging for audit trail

4. **Quality Gates**: Data must pass checks before trading
   - Staleness detection
   - Gap identification
   - Anomaly flagging

---

## 🗺️ Roadmap

### In Progress

- [ ] Alternative data integration (sentiment, macro indicators)
- [ ] Ensemble methods combining multiple weak signals
- [ ] Intraday strategies with finer granularity

### Future Work

- [ ] Options strategies (covered calls, protective puts)
- [ ] Multi-asset allocation (equities, bonds, commodities)
- [ ] Live trading integration (Zerodha Kite API)
- [ ] Real-time monitoring dashboard
- [ ] Automated strategy discovery via genetic programming

---

## 📚 Project Structure Details

### Data Schema

All OHLCV data validated with Pandera schemas:

- **Timestamp**: UTC timezone-aware
- **OHLC**: Positive floats
- **Volume**: Non-negative integers
- **Sorted**: Chronological order enforced

### Cost Model

Realistic NSE equity delivery costs (₹):

- **Brokerage**: ₹20 or 0.1% (lower of the two), min ₹5
- **STT**: 0.1% (both sides)
- **Stamp Duty**: 0.015% (buy only)
- **Exchange**: 0.00297% (NSE charges)
- **SEBI**: 0.0001%
- **GST**: 18% on brokerage + exchange + SEBI
- **Slippage**: 0.05% adverse movement per trade

### Walk-Forward Protocol

Prevents look-ahead bias:

1. Label at row `t` uses opens from `t+1` to `t+6`
2. Training data: rows where `label_end < test_period_start`
3. Purging: No training on data whose outcome overlaps test period
4. One model retrained yearly across all stocks

---

## 🤝 Contributing

This is a personal research project, but feedback is welcome:

- Found a bug? Open an issue
- Have a strategy idea? Share it in discussions
- Want to collaborate? Reach out

**Philosophy**: Honest research over hype. Every contribution must maintain integrity:

- Pre-register experiments before running
- Log all results (good and bad)
- Never tune on test data
- Document assumptions and limitations

---

## 📄 License

This project is for educational and research purposes. Not financial advice.

**Disclaimer**: Past performance does not guarantee future results. All strategies shown have failed to beat benchmarks. Use at your own risk.

---

## 🙏 Acknowledgments

- **Data**: Yahoo Finance (yfinance)
- **ML**: XGBoost, scikit-learn
- **Tracking**: MLflow
- **Inspiration**: Quantitative finance research emphasizing reproducibility and honest evaluation

---

<div align="center">

**Built with 🧪 scientific rigor and 🛡️ safety-first principles**

_"The market can remain irrational longer than you can remain solvent."_ — John Maynard Keynes

⭐ Star this repo if you appreciate honest quantitative research

</div>
