from __future__ import annotations

from typing import Any

from fraud_lab.features.feature_contract import MODEL_VERSION, FEATURE_VERSION
from fraud_lab.model.rules import clamp_score, decision_from_score


class ModelEndpointSimulator:
    """Simula un SageMaker Real-Time Endpoint que recibe features model-ready."""

    def predict(self, feature_vector: dict[str, float], request_id: str = "") -> dict[str, Any]:
        amount = float(feature_vector.get("amount_normalized", 0.0))
        user_avg = max(float(feature_vector.get("user_avg_amount_30d", 0.0)), 1.0)
        amount_ratio = amount / user_avg
        card_txn_count_5m = float(feature_vector.get("card_txn_count_5m", 0.0))
        declined = float(feature_vector.get("card_declined_count_1h", 0.0))
        merchant_risk = float(feature_vector.get("merchant_risk_score", 0.0))
        device_trust = float(feature_vector.get("device_trust_score", 1.0))
        device_users = float(feature_vector.get("device_users_count_7d", 0.0))
        cross_border = float(feature_vector.get("is_cross_border", 0.0))
        weekend = float(feature_vector.get("is_weekend", 0.0))

        score = 0.06
        score += min(amount / 2500.0, 0.20)
        score += 0.22 if amount_ratio > 3.0 else min(amount_ratio / 20.0, 0.10)
        score += min(card_txn_count_5m * 0.06, 0.18)
        score += min(declined * 0.08, 0.18)
        score += merchant_risk * 0.24
        score += max(0.0, 1.0 - device_trust) * 0.18
        score += min(device_users * 0.015, 0.12)
        score += cross_border * 0.10
        score += weekend * 0.03
        score = clamp_score(score)

        reason_codes: list[str] = []
        if amount_ratio > 3.0:
            reason_codes.append("high_amount_vs_user_avg")
        if merchant_risk >= 0.6:
            reason_codes.append("risky_merchant")
        if device_trust <= 0.4 or device_users >= 5:
            reason_codes.append("new_or_risky_device")
        if card_txn_count_5m >= 3:
            reason_codes.append("high_card_velocity")
        if declined > 0:
            reason_codes.append("recent_declines")
        if cross_border:
            reason_codes.append("cross_border_transaction")
        if not reason_codes:
            reason_codes.append("baseline_risk")

        return {
            "fraud_score": score,
            "decision": decision_from_score(score),
            "reason_codes": reason_codes,
            "model_version": MODEL_VERSION,
            "feature_version": FEATURE_VERSION,
            "request_id": request_id,
        }

