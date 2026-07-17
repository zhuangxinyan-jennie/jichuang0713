"""轻量性能预测器 (第一阶段: RandomForest; 对齐 HGBO HGP 的早期预测角色)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor

from hgbo_optune.hpp.feature_encoder import FEATURE_NAMES, features_to_vector


@dataclass
class PerformancePredictor:
    model: Optional[RandomForestRegressor] = None
    feature_names: List[str] = field(default_factory=lambda: FEATURE_NAMES.copy())
    min_samples: int = 8

    def fit(self, feature_rows: List[Dict[str, float]], latency_ms: List[float]) -> None:
        if len(feature_rows) < self.min_samples:
            raise ValueError(
                f"Need at least {self.min_samples} samples to train HPP, got {len(feature_rows)}"
            )
        x = np.array([features_to_vector(row) for row in feature_rows], dtype=np.float64)
        y = np.array(latency_ms, dtype=np.float64)
        self.model = RandomForestRegressor(
            n_estimators=100,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(x, y)

    def predict(self, feature_row: Dict[str, float]) -> float:
        if self.model is None:
            raise RuntimeError("HPP model is not trained")
        x = np.array([features_to_vector(feature_row)], dtype=np.float64)
        return float(self.model.predict(x)[0])

    def save(self, path: Path) -> None:
        if self.model is None:
            raise RuntimeError("No trained model to save")
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "feature_names": self.feature_names}, path)

    @classmethod
    def load(cls, path: Path) -> "PerformancePredictor":
        payload = joblib.load(path)
        predictor = cls(model=payload["model"], feature_names=payload["feature_names"])
        return predictor
