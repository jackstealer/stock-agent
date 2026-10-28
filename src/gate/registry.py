from collections import Counter
from pathlib import Path

import yaml


def load_trials(path="docs/trials.yaml") -> list:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["trials"]


def mlflow_run_names(experiment="stock-agent", uri="sqlite:///mlflow.db") -> list:
    """Names of ALL runs, including deleted ones: deleting a run must not hide a trial."""
    import mlflow
    from mlflow.entities import ViewType

    mlflow.set_tracking_uri(uri)
    runs = mlflow.search_runs(experiment_names=[experiment],
                              run_view_type=ViewType.ALL)
    if runs.empty:
        return []
    return runs["tags.mlflow.runName"].fillna("<unnamed>").tolist()


def compare(registered: list, logged: list) -> list:
    """Problems between the registry and MLflow. An empty list means they agree."""
    reg, log = Counter(registered), Counter(logged)
    problems = [f"{n} MLflow run(s) named '{name}' are not in the registry"
                for name, n in (log - reg).items()]
    problems += [f"registry lists '{name}' x{n} but MLflow has fewer "
                 "(deleted or renamed?)" for name, n in (reg - log).items()]
    return problems