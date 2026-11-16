"""What a result has to beat: passive holding and chance."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pandas as pd

from signal_audit.audit.backtest import BacktestConfig, open_to_open_returns, run_backtest
from signal_audit.audit.metrics import sharpe
from signal_audit.data.market import MarketData
from signal_audit.signals.base import align_scores


def buy_and_hold(data: MarketData) -> pd.Series:
    """Equal-weight basket of every ticker, rebalanced daily, before costs."""
    return open_to_open_returns(data).mean(axis=1).iloc[:-1]


@dataclass(frozen=True)
class PermutationResult:
    observed_sharpe: float
    null_sharpes: npt.NDArray[np.float64]
    p_value: float

    @property
    def n_permutations(self) -> int:
        return len(self.null_sharpes)


def permutation_test(
    scores: pd.DataFrame,
    data: MarketData,
    config: BacktestConfig,
    rng: np.random.Generator,
    n_permutations: int = 500,
) -> PermutationResult:
    """Could shuffled scores have done as well?

    The date order of the score matrix is shuffled, which keeps each day's
    cross-section intact but destroys its link to what happened next. The test
    is run before costs: shuffling raises turnover, so including costs would
    penalise the null and flatter the signal. Costs are judged separately.

    The p-value is (1 + number of shuffles at least as good) / (N + 1).
    """
    if n_permutations < 1:
        raise ValueError("n_permutations must be at least 1")

    gross_config = BacktestConfig(top_k=config.top_k, cost_bps=0.0)
    aligned = align_scores(scores, data)
    observed = sharpe(run_backtest(aligned, data, gross_config).returns)

    values = aligned.to_numpy()
    null = np.empty(n_permutations, dtype=np.float64)
    for i in range(n_permutations):
        shuffled = pd.DataFrame(
            values[rng.permutation(len(values))], index=aligned.index, columns=aligned.columns
        )
        null[i] = sharpe(run_backtest(shuffled, data, gross_config).returns)

    p_value = (1 + int((null >= observed).sum())) / (n_permutations + 1)
    return PermutationResult(observed_sharpe=observed, null_sharpes=null, p_value=p_value)
