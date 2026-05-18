from __future__ import annotations

from pathlib import Path
from typing import Any


class FraudFallbackModel:
    """Modelo deterministico simple si joblib no puede cargar el artefacto."""

    def predict_proba(self, rows: list[list[float]]) -> list[list[float]]:
        results: list[list[float]] = []
        for row in rows:
            amount = float(row[0]) if row else 0.0
            merchant_risk = float(row[18]) if len(row) > 18 else 0.0
            device_trust = float(row[20]) if len(row) > 20 else 0.5
            score = min(0.98, max(0.02, 0.15 + amount / 2000.0 + merchant_risk * 0.35 - device_trust * 0.2))
            results.append([1.0 - score, score])
        return results


def model_fn(model_dir: str) -> Any:
    model_path = Path(model_dir) / "model.joblib"
    if model_path.exists():
        try:
            import joblib

            return joblib.load(model_path)
        except Exception:
            return FraudFallbackModel()
    return FraudFallbackModel()
