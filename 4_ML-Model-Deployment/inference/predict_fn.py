from __future__ import annotations

from typing import Any


def _score_to_decision(score: float) -> str:
    if score >= 0.75:
        return "review"
    if score >= 0.5:
        return "monitor"
    return "approve"


def predict_fn(input_data: list[list[float]], model: Any) -> list[dict[str, Any]]:
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(input_data)
        scores = [float(row[1]) for row in probabilities]
    elif hasattr(model, "predict"):
        predictions = model.predict(input_data)
        scores = [float(value) for value in predictions]
    else:
        scores = [0.5 for _ in input_data]

    results: list[dict[str, Any]] = []
    for score in scores:
        score = max(0.0, min(1.0, float(score)))
        results.append(
            {
                "score": score,
                "predicted_label": int(score >= 0.5),
                "decision": _score_to_decision(score),
            }
        )
    return results
