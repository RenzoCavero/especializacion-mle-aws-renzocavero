from __future__ import annotations


def decision_from_score(score: float) -> str:
    if score >= 0.80:
        return "reject"
    if score >= 0.50:
        return "manual_review"
    return "approve"


def clamp_score(score: float) -> float:
    return round(max(0.0, min(1.0, float(score))), 4)

