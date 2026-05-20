from __future__ import annotations

from typing import Any


MODEL_VERSION = "fraud_model_v1"
FEATURE_VERSION = "fraud_features_v1"


def _decision(score: float) -> str:
    if score >= 0.8:
        return "reject"
    if score >= 0.5:
        return "manual_review"
    return "approve"


def _reason_codes(row: list[float], score: float) -> list[str]:
    reasons: list[str] = []
    if len(row) > 14 and row[0] > max(row[14] * 3.0, 300.0):
        reasons.append("high_amount_vs_user_avg")
    if len(row) > 18 and row[18] >= 0.6:
        reasons.append("risky_merchant")
    if len(row) > 20 and row[20] <= 0.45:
        reasons.append("new_or_risky_device")
    if len(row) > 16 and row[16] >= 2:
        reasons.append("recent_card_declines")
    if not reasons and score >= 0.5:
        reasons.append("combined_risk_signal")
    return reasons


def predict_fn(input_data: list[list[float]], model: Any) -> list[dict[str, Any]]:
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(input_data)
        scores = [float(row[1]) for row in probabilities]
    elif hasattr(model, "predict"):
        scores = [float(value) for value in model.predict(input_data)]
    else:
        scores = [0.5 for _ in input_data]

    results: list[dict[str, Any]] = []
    for row, score in zip(input_data, scores):
        score = max(0.0, min(1.0, float(score)))
        results.append(
            {
                "fraud_score": score,
                "score": score,
                "predicted_label": int(score >= 0.5),
                "decision": _decision(score),
                "reason_codes": _reason_codes(row, score),
                "model_version": MODEL_VERSION,
                "feature_version": FEATURE_VERSION,
            }
        )
    return results

