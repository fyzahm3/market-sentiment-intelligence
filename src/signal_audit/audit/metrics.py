"""Performance statistics, including multiple-testing-aware Sharpe ratios.

Probabilistic and deflated Sharpe ratios follow Bailey & Lopez de Prado,
"The Deflated Sharpe Ratio" (2014).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from pydantic import BaseModel
from scipy import stats

TRADING_DAYS = 252
_EULER_GAMMA = 0.5772156649015329
_MIN_DEVIATION = 1e-12


class PerformanceSummary(BaseModel):
    total_return: float
    cagr: float
    annual_volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    mean_daily_turnover: float | None = None


def _per_period_sharpe(returns: pd.Series) -> float:
    deviation = float(returns.std(ddof=1))
    # A constant series has a deviation of floating-point dust, not exactly zero.
    if len(returns) < 2 or math.isnan(deviation) or deviation < _MIN_DEVIATION:
        return 0.0
    return float(returns.mean()) / deviation


def sharpe(returns: pd.Series, periods: int = TRADING_DAYS) -> float:
    return _per_period_sharpe(returns) * math.sqrt(periods)


def sortino(returns: pd.Series, periods: int = TRADING_DAYS) -> float:
    downside = returns[returns < 0]
    if len(downside) < 2:
        return 0.0
    deviation = float(np.sqrt((downside**2).mean()))
    if deviation == 0.0:
        return 0.0
    return float(returns.mean()) / deviation * math.sqrt(periods)


def total_return(returns: pd.Series) -> float:
    return float(np.prod(1.0 + returns.to_numpy(dtype=float))) - 1.0


def cagr(returns: pd.Series, periods: int = TRADING_DAYS) -> float:
    if len(returns) == 0:
        return 0.0
    growth = 1.0 + total_return(returns)
    if growth <= 0:
        return -1.0
    return float(growth ** (periods / len(returns)) - 1.0)


def max_drawdown(returns: pd.Series) -> float:
    if len(returns) == 0:
        return 0.0
    equity = (1.0 + returns).cumprod()
    peak = equity.cummax().clip(lower=1.0)
    return float((equity / peak - 1.0).min())


def summarize(returns: pd.Series, turnover: pd.Series | None = None) -> PerformanceSummary:
    return PerformanceSummary(
        total_return=total_return(returns),
        cagr=cagr(returns),
        annual_volatility=float(returns.std(ddof=1)) * math.sqrt(TRADING_DAYS),
        sharpe=sharpe(returns),
        sortino=sortino(returns),
        max_drawdown=max_drawdown(returns),
        mean_daily_turnover=None if turnover is None else float(turnover.mean()),
    )


def probabilistic_sharpe_ratio(returns: pd.Series, benchmark_sharpe: float = 0.0) -> float:
    """Probability that the true per-period Sharpe exceeds ``benchmark_sharpe``.

    ``benchmark_sharpe`` is per period (not annualised). Accounts for sample
    length, skewness and fat tails.
    """
    n = len(returns)
    if n < 3:
        return 0.5
    observed = _per_period_sharpe(returns)
    skew = float(stats.skew(returns, bias=False))
    kurt = float(stats.kurtosis(returns, fisher=False, bias=False))
    variance_term = 1.0 - skew * observed + (kurt - 1.0) / 4.0 * observed**2
    if variance_term <= 0:
        return 0.5
    z = (observed - benchmark_sharpe) * math.sqrt(n - 1) / math.sqrt(variance_term)
    return float(stats.norm.cdf(z))


def expected_max_sharpe(n_trials: int, sharpe_variance: float) -> float:
    """Expected best per-period Sharpe among ``n_trials`` strategies with no skill."""
    if n_trials < 1:
        raise ValueError("n_trials must be at least 1")
    if n_trials == 1:
        return 0.0
    first = stats.norm.ppf(1.0 - 1.0 / n_trials)
    second = stats.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    return float(math.sqrt(sharpe_variance) * ((1 - _EULER_GAMMA) * first + _EULER_GAMMA * second))


def deflated_sharpe_ratio(
    returns: pd.Series, n_trials: int = 1, sharpe_variance: float | None = None
) -> float:
    """Probability the true Sharpe is positive after allowing for ``n_trials`` attempts.

    ``sharpe_variance`` is the variance of per-period Sharpe estimates across
    the trials. When it is not supplied, the sampling variance of a zero-skill
    strategy, 1 / (n - 1), is used.
    """
    n = len(returns)
    if n < 3:
        return 0.5
    variance = sharpe_variance if sharpe_variance is not None else 1.0 / (n - 1)
    hurdle = expected_max_sharpe(n_trials, variance)
    return probabilistic_sharpe_ratio(returns, benchmark_sharpe=hurdle)
