from typing import Any, Dict, Optional

import numpy
from optuna import distributions
from optuna.samplers import BaseSampler
from optuna.study import Study
from optuna.trial import FrozenTrial


class LatinHypercubeSampler(BaseSampler):
    """参考 HGBO-DSE bome/alg/lhs_sampler.py."""

    def __init__(self, init_params: Optional[Dict[str, Any]] = None, seed: Optional[int] = None) -> None:
        self._rng = numpy.random.RandomState(seed)
        self._init_params = init_params or {}

    def reseed_rng(self) -> None:
        self._rng.seed()

    def infer_relative_search_space(
        self, study: Study, trial: FrozenTrial
    ) -> Dict[str, distributions.BaseDistribution]:
        return {}

    def sample_relative(
        self,
        study: Study,
        trial: FrozenTrial,
        search_space: Dict[str, distributions.BaseDistribution],
    ) -> Dict[str, Any]:
        return {}

    def sample_independent(
        self,
        study: Study,
        trial: FrozenTrial,
        param_name: str,
        param_distribution: distributions.BaseDistribution,
    ) -> Any:
        if param_name not in self._init_params:
            raise KeyError(f"Missing LHS init value for {param_name}")
        idx = trial.number
        values = self._init_params[param_name]
        if idx >= len(values):
            raise IndexError(f"LHS index {idx} out of range for {param_name}")
        return values[idx]
