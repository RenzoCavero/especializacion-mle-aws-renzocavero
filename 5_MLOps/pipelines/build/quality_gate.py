"""Quality gate rules for candidate models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    reasons: list[str]
    metrics: dict[str, float]


def evaluate_quality_gate(
    metrics: dict[str, float],
    f1_threshold: float = 0.70,
    auc_threshold: float = 0.70,
) -> QualityGateResult:
    reasons: list[str] = []
    f1 = float(metrics.get("f1", 0.0))
    auc = float(metrics.get("auc", 0.0))
    if f1 < f1_threshold:
        reasons.append(f"f1={f1:.4f} is below threshold {f1_threshold:.4f}")
    if auc < auc_threshold:
        reasons.append(f"auc={auc:.4f} is below threshold {auc_threshold:.4f}")
    return QualityGateResult(passed=not reasons, reasons=reasons, metrics={"f1": f1, "auc": auc})


def approval_status_for_metrics(metrics: dict[str, float], f1_threshold: float = 0.70, auc_threshold: float = 0.70) -> str:
    result = evaluate_quality_gate(metrics, f1_threshold=f1_threshold, auc_threshold=auc_threshold)
    return "Approved" if result.passed else "Rejected"

