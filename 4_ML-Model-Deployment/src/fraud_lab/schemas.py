from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScoringResult:
    transaction_id: str
    request_id: str
    fraud_score: float
    decision: str
    reason_codes: list[str]
    model_version: str
    feature_version: str
    latency_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "request_id": self.request_id,
            "fraud_score": self.fraud_score,
            "decision": self.decision,
            "reason_codes": self.reason_codes,
            "model_version": self.model_version,
            "feature_version": self.feature_version,
            "latency_ms": self.latency_ms,
        }


@dataclass
class FeatureVector:
    transaction_id: str
    event_time: str
    values: dict[str, float]
    ordered_values: list[float]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "event_time": self.event_time,
            "features": self.values,
            "ordered_values": self.ordered_values,
            "warnings": self.warnings,
        }

