from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from signal_audit.audit import metrics


def test_sharpe_matches_definition() -> None:
    returns = pd.Series([0.01, -0.005, 0.02, 0.0, 0.005])
    expected = returns.mean() / returns.std(ddof=1) * math.sqrt(252)
    assert metrics.sharpe(returns) == pytest.approx(expected)


def test_sharpe_of_constant_series_is_zero() -> None:
    assert metrics.sharpe(pd.Series([0.01] * 10)) == 0.0


def test_max_drawdown() -> None:
    # 1.0 -> 1.1 -> 0.88 -> 0.968: worst fall is 20% from the peak.
    returns = pd.Series([0.10, -0.20, 0.10])
    assert metrics.max_drawdown(returns) == pytest.approx(-0.20)


def test_max_drawdown_counts_losses_from_the_start() -> None:
    assert metrics.max_drawdown(pd.Series([-0.10, -0.10])) == pytest.approx(-0.19)


def test_total_return_and_cagr() -> None:
    returns = pd.Series([0.01] * 252)
    assert metrics.total_return(returns) == pytest.approx(1.01**252 - 1)
    assert metrics.cagr(returns) == pytest.approx(1.01**252 - 1)


def test_probabilistic_sharpe_is_half_for_zero_mean() -> None:
    rng = np.random.default_rng(0)
    returns = pd.Series(rng.normal(0, 0.01, 2000))
    returns = returns - returns.mean()
    assert metrics.probabilistic_sharpe_ratio(returns) == pytest.approx(0.5, abs=1e-6)


def test_expected_max_sharpe_grows_with_trials() -> None:
    assert metrics.expected_max_sharpe(1, 0.01) == 0.0
    few = metrics.expected_max_sharpe(10, 0.01)
    many = metrics.expected_max_sharpe(1000, 0.01)
    assert 0 < few < many


def test_deflated_sharpe_falls_as_trials_rise() -> None:
    rng = np.random.default_rng(1)
    returns = pd.Series(rng.normal(0.001, 0.01, 500))
    one = metrics.deflated_sharpe_ratio(returns, n_trials=1)
    hundred = metrics.deflated_sharpe_ratio(returns, n_trials=100)
    assert one == pytest.approx(metrics.probabilistic_sharpe_ratio(returns))
    assert hundred < one


def test_expected_max_sharpe_rejects_zero_trials() -> None:
    with pytest.raises(ValueError):
        metrics.expected_max_sharpe(0, 0.01)
