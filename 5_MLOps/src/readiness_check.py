"""Generate an MLOps readiness checklist."""

from __future__ import annotations

import json
from pathlib import Path

from .config import load_config, read_metadata


CHECKS = {
    "datos": ["data_generation", "data_upload"],
    "pipeline": ["pipeline_definition", "pipeline_execution"],
    "registry": ["model_registry", "approved_model"],
    "approval": ["model_approval"],
    "deployment": ["endpoint_deployment", "smoke_test"],
    "monitoring": ["baseline", "monitoring_schedule"],
    "drift": ["traffic_drift", "monitoring_results"],
    "model_quality": ["model_quality_capture", "model_quality_baseline", "model_quality_schedule", "model_quality_alarm"],
    "alarms": ["cloudwatch_alarm"],
    "feedback_loop": ["eventbridge_rule", "feedback_loop"],
    "retraining": ["retraining_decision"],
    "rollback": ["rollback_plan"],
    "seguridad": [],
    "costos": [],
    "documentacion": [],
}


def run_readiness_check() -> dict[str, object]:
    config = load_config(validate=False)
    results = {}
    for check, metadata_names in CHECKS.items():
        if not metadata_names:
            results[check] = {"status": "documented", "metadata": []}
            continue
        available = [name for name in metadata_names if read_metadata(config, name)]
        results[check] = {
            "status": "ready" if available else "pending",
            "metadata": available,
            "expected": metadata_names,
        }
    payload = {
        "lab_mode": config.lab_mode,
        "independent_from_lab_4": config.is_standalone or config.is_integrated,
        "automatic_retraining_enabled": config.enable_automatic_retraining,
        "checks": results,
    }
    path = config.local_outputs_dir / "readiness_check.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md = config.local_outputs_dir / "readiness_check.md"
    lines = ["# MLOps Readiness Check", ""]
    for name, result in results.items():
        lines.append(f"- {name}: {result['status']}")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return payload


if __name__ == "__main__":
    run_readiness_check()
