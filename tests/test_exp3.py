import numpy as np
import pandas as pd

from src.models.evaluate_exp3 import momentum_score, trend_signal


def make_prices(n_up=300, n_down=100):
    idx = pd.bdate_range("2022-01-03", periods=n_up + n_down, tz="Asia/Kolkata")
    p = np.concatenate([100 * 1.002 ** np.arange(n_up),
                        100 * 1.002 ** (n_up - 1) * 0.99 ** np.arange(1, n_down + 1)])
    return pd.DataFrame({"A": p, "B": p}, index=idx)


def test_trend_is_cash_in_warmup_invested_in_uptrend_and_cash_after_crash():
    sig = trend_signal(make_prices())
    assert (sig.iloc[:199] == 0).all()        # no 200-day average yet: cash
    assert sig.iloc[280] == 1.0               # steady uptrend: invested
    assert sig.iloc[-1] == 0.0                # after the slide: cash


def test_trend_signal_only_changes_on_the_last_trading_day_of_a_week():
    C = make_prices()
    sig = trend_signal(C)
    wk = C.index.isocalendar().week.to_numpy()
    changed = np.where(sig.diff().fillna(0).to_numpy() != 0)[0]
    assert len(changed) > 0
    for i in changed:
        assert i == len(C) - 1 or wk[i + 1] != wk[i]


def test_signals_never_use_future_prices():
    C = make_prices()
    C2 = C.copy()
    C2.iloc[350:] *= 3                         # rewrite the future
    pd.testing.assert_series_equal(trend_signal(C).iloc[:350], trend_signal(C2).iloc[:350])
    pd.testing.assert_frame_equal(momentum_score(C).iloc[:350],
                                  momentum_score(C2).iloc[:350])