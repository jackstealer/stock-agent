# Promotion gate: rules

Changed only through a pull request with a written reason. Never by the strategy
code, never during an experiment, never after seeing a result.

A candidate may receive ONE look at the locked test split only if ALL hold:
1. Trial registry: every run in MLflow experiment "stock-agent" (including deleted
   runs) is listed in docs/trials.yaml, and the registry lists nothing MLflow lacks.
2. At least 500 daily observations of net returns for the candidate and its benchmark.
3. Deflated Sharpe ratio of the daily ACTIVE returns (candidate minus benchmark) is at
   least 0.95, given the number of registered trials. Between-trial Sharpe variance is
   fixed at an annualised standard deviation of 0.5 (an assumption chosen up front,
   not measured).
4. Mean active return is positive in both halves of the sample.

Passing grants one test-split look, logged in docs/experiments.md. It is not proof of
skill. Failing is logged. Parameters are not changed to turn a failure into a pass.