import re

import mlflow


def _clean(s: str) -> str:
    return re.sub(r"\W+", "_", s).strip("_")


def log_run(run_name: str, params: dict, aucs: dict, table) -> None:
    """Log one walk-forward evaluation. Every run is one counted experiment."""
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("stock-agent")
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({k: str(v) for k, v in params.items()})
        for year, auc in aucs.items():
            mlflow.log_metric(f"auc_{year}", float(auc))
        for strat, row in table.iterrows():
            for k in ("total_return", "cagr", "sharpe", "max_drawdown",
                      "trades", "fees", "slippage", "invested"):
                if k in table.columns:
                    mlflow.log_metric(f"{_clean(strat)}__{k}", float(row[k]))