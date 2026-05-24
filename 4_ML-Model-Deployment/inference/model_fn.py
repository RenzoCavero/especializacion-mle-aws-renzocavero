from __future__ import annotations

from pathlib import Path
from typing import Any


class RuleBasedFallbackModel:
    feature_names = [
        "age",
        "income",
        "account_tenure_months",
        "monthly_spend",
        "support_tickets_90d",
    ]

    def predict_proba(self, rows: list[list[float]]) -> list[list[float]]:
        results: list[list[float]] = []
        for row in rows:
            age, income, tenure, spend, tickets = row[:5]
            raw = (
                0.02 * (age - 35)
                - 0.00001 * (income - 50000)
                - 0.015 * tenure
                + 0.002 * spend
                + 0.18 * tickets
            )
            score = 1.0 / (1.0 + pow(2.718281828, -raw))
            score = max(0.0, min(1.0, score))
            results.append([1.0 - score, score])
        return results


def model_fn(model_dir: str) -> Any:
    model_path = Path(model_dir) / "model.joblib"
    if model_path.exists():
        try:
            import joblib

            return joblib.load(model_path)
        except Exception:
            return RuleBasedFallbackModel()
    return RuleBasedFallbackModel()
