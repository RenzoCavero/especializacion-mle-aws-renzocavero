"""Diagnose a monitoring alert and recommend one controlled action."""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone


DATA_QUALITY_SEVERITY = {
    "none": "0 violations",
    "low": "1 violation",
    "medium": "2-4 violations",
    "high": "5-9 violations",
    "critical": "10+ violations",
}

MODEL_QUALITY_SEVERITY = {
    "none": "F1 is at or above threshold",
    "low": "F1 degradation is greater than 0% and below 10%",
    "medium": "F1 degradation is 10% to below 25%",
    "high": "F1 degradation is 25% to below 50%",
    "critical": "F1 degradation is 50% or higher",
}


def _safe_float(value, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    parsed = _safe_float(value)
    if parsed is None:
        return default
    return int(round(parsed))


def _reason_data(detail: dict) -> dict:
    state = detail.get("state", {}) if isinstance(detail, dict) else {}
    raw = state.get("reasonData", "") if isinstance(state, dict) else ""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _latest_datapoint(reason_data: dict) -> float | None:
    values = reason_data.get("recentDatapoints", [])
    if not isinstance(values, list) or not values:
        return None
    return _safe_float(values[-1])


def _metric_info(detail: dict) -> dict:
    metrics = detail.get("configuration", {}).get("metrics", []) if isinstance(detail, dict) else []
    if not isinstance(metrics, list) or not metrics:
        return {}
    metric = metrics[0].get("metricStat", {}).get("metric", {})
    return metric if isinstance(metric, dict) else {}


def _metric_dimensions(metric: dict) -> dict:
    dimensions = metric.get("dimensions", {})
    return dimensions if isinstance(dimensions, dict) else {}


def _data_quality_severity(violations_count: int) -> str:
    if violations_count >= 10:
        return "critical"
    if violations_count >= 5:
        return "high"
    if violations_count >= 2:
        return "medium"
    if violations_count == 1:
        return "low"
    return "none"


def _model_quality_severity(f1_value: float | None, threshold: float) -> tuple[str, float]:
    if f1_value is None or threshold <= 0:
        return "medium", 0.0
    degradation = max(0.0, (threshold - f1_value) / threshold)
    if degradation <= 0:
        return "none", 0.0
    if degradation >= 0.50:
        return "critical", degradation
    if degradation >= 0.25:
        return "high", degradation
    if degradation >= 0.10:
        return "medium", degradation
    return "low", degradation


def _alarm_type(alarm_name: str, metric_name: str) -> str:
    value = f"{alarm_name} {metric_name}".lower()
    if "model-quality" in value or "modelquality" in value or metric_name.lower() == "f1":
        return "model_quality"
    if "data-quality" in value or "dataquality" in value or "drift" in value or "violations" in value:
        return "data_quality"
    return "unknown"


def _decide(violations_count: int, severity: str, automatic_retraining: bool) -> str:
    severity = severity.lower()
    if violations_count <= 0:
        return "no_action"
    if severity in {"critical", "high"}:
        return "retraining" if automatic_retraining else "human_review"
    if severity == "medium":
        return "baseline_update"
    return "human_review"


def _diagnose_event(event: dict) -> dict:
    detail = event.get("detail", {}) if isinstance(event, dict) else {}
    metric = _metric_info(detail)
    dimensions = _metric_dimensions(metric)
    alarm_name = str(event.get("alarm_name") or detail.get("alarmName") or os.getenv("ALARM_NAME", ""))
    metric_name = str(metric.get("name") or event.get("metric_name") or "")
    endpoint_name = str(
        event.get("endpoint_name")
        or dimensions.get("EndpointName")
        or dimensions.get("Endpoint")
        or dimensions.get("BatchMonitoringSchedule")
        or dimensions.get("BatchTransformJobName")
        or dimensions.get("BatchModelName")
        or os.getenv("ENDPOINT_NAME", "")
    )
    reason_data = _reason_data(detail)
    datapoint = _latest_datapoint(reason_data)
    threshold = _safe_float(reason_data.get("threshold"))
    alarm_type = _alarm_type(alarm_name, metric_name)

    diagnosis = {
        "alarm_name": alarm_name,
        "endpoint_name": endpoint_name,
        "alarm_type": alarm_type,
        "metric_name": metric_name,
        "metric_value": datapoint,
        "metric_threshold": threshold,
        "severity_source": "event_payload",
    }

    if alarm_type == "data_quality":
        violations_count = _safe_int(event.get("violations_count") or detail.get("violations_count"), 0)
        if datapoint is not None:
            violations_count = _safe_int(datapoint, violations_count)
            diagnosis["severity_source"] = "cloudwatch_datapoint"
        severity = str(event.get("severity") or detail.get("severity") or _data_quality_severity(violations_count))
        diagnosis.update(
            {
                "violations_count": violations_count,
                "severity": severity,
                "severity_rule": DATA_QUALITY_SEVERITY,
            }
        )
        return diagnosis

    if alarm_type == "model_quality":
        threshold = threshold if threshold is not None else _safe_float(os.getenv("MODEL_QUALITY_F1_THRESHOLD"), 0.7)
        severity, degradation = _model_quality_severity(datapoint, float(threshold or 0.7))
        if event.get("severity") or detail.get("severity"):
            severity = str(event.get("severity") or detail.get("severity"))
        diagnosis.update(
            {
                "violations_count": 1 if severity != "none" else 0,
                "severity": severity,
                "severity_rule": MODEL_QUALITY_SEVERITY,
                "model_quality_f1": datapoint,
                "model_quality_f1_threshold": threshold,
                "model_quality_degradation_pct": round(degradation * 100, 2),
                "severity_source": "f1_degradation_pct",
            }
        )
        return diagnosis

    diagnosis.update(
        {
            "violations_count": _safe_int(event.get("violations_count") or detail.get("violations_count"), 1),
            "severity": str(event.get("severity") or detail.get("severity") or "medium"),
            "severity_rule": "unknown_alarm_defaults_to_manual_or_medium",
        }
    )
    return diagnosis


def lambda_handler(event, context):
    event = event if isinstance(event, dict) else {}
    diagnosis = _diagnose_event(event)
    violations_count = int(diagnosis["violations_count"])
    severity = str(diagnosis["severity"])
    automatic = os.getenv("ENABLE_AUTOMATIC_RETRAINING", "false").lower() == "true"
    explicit_action = str(event.get("recommended_action") or "")
    allowed_actions = {"retraining", "rollback", "baseline_update", "human_review", "no_action"}
    action = explicit_action if explicit_action in allowed_actions else _decide(violations_count, severity, automatic)
    return {
        "diagnosed_at": datetime.now(timezone.utc).isoformat(),
        "alarm_name": diagnosis["alarm_name"],
        "endpoint_name": diagnosis["endpoint_name"],
        "alarm_type": diagnosis["alarm_type"],
        "violations_count": violations_count,
        "severity": severity,
        "diagnosis": diagnosis,
        "automatic_retraining_enabled": automatic,
        "recommended_action": action,
        "evidence": event,
    }
