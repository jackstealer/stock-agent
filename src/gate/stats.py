import numpy as np
from scipy.stats import kurtosis, norm, skew

EULER = 0.5772156649015329


def sharpe_daily(r) -> float:
    r = np.asarray(r, dtype=float)
    sd = r.std(ddof=1) if len(r) > 1 else 0.0
    return float(r.mean() / sd) if sd > 0 else 0.0


def prob_sharpe(r, sr_star: float = 0.0) -> float:
    """Probabilistic Sharpe ratio: the chance the true daily Sharpe exceeds sr_star,
    accounting for sample length, skew and fat tails (Bailey and Lopez de Prado)."""
    r = np.asarray(r, dtype=float)
    if len(r) < 3 or r.std(ddof=1) == 0:
        return 0.0
    sr = sharpe_daily(r)
    g3, g4 = skew(r), kurtosis(r, fisher=False)
    denom = np.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2, 1e-12))
    return float(norm.cdf((sr - sr_star) * np.sqrt(len(r) - 1) / denom))


def expected_max_sharpe(n_trials: int, var_sr: float) -> float:
    """Daily Sharpe the best of n_trials unskilled strategies would be expected to
    show by luck alone. This is the hurdle that rises with every experiment."""
    if n_trials < 2:
        return 0.0
    return float(np.sqrt(var_sr) * ((1 - EULER) * norm.ppf(1 - 1 / n_trials)
                                    + EULER * norm.ppf(1 - 1 / (n_trials * np.e))))


def deflated_sharpe(r, n_trials: int, var_sr: float) -> float:
    return prob_sharpe(r, expected_max_sharpe(n_trials, var_sr))