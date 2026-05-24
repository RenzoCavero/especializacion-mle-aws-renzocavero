"""Generate the local MLOps report."""

from __future__ import annotations

import json
from pathlib import Path

from .config import load_config, read_metadata


SECTIONS = [
    ("Pipeline build", "pipeline_execution_status"),
    ("Model Registry", "model_registry"),
    ("Approval status", "model_approval"),
    ("Endpoint", "endpoint_deployment"),
    ("Data capture", "data_capture"),
    ("Baseline", "baseline"),
    ("Monitoring schedule", "monitoring_schedule"),
    ("Violations", "monitoring_results"),
    ("Model quality capture", "model_quality_capture"),
    ("Model quality baseline", "model_quality_baseline"),
    ("Model quality schedule", "model_quality_schedule"),
    ("Model quality alarm", "model_quality_alarm"),
    ("CloudWatch alarm", "cloudwatch_alarm"),
    ("EventBridge rule", "eventbridge_rule"),
    ("Feedback loop", "feedback_loop"),
    ("Batch transform", "batch_transform"),
    ("Batch transform capture", "batch_transform_capture"),
    ("Batch monitoring schedule", "batch_monitoring_schedule"),
    ("Custom batch data quality schedule", "custom_batch_data_quality_schedule"),
    ("Custom batch data quality job", "custom_batch_data_quality_job"),
    ("Batch data quality alarm", "batch_cloudwatch_alarm"),
]


def generate_report() -> Path:
    config = load_config(validate=False)
    path = config.local_outputs_dir / "mlops_report.md"
    lines = [
        "# MLOps Report",
        "",
        f"- LAB_MODE: `{config.lab_mode}`",
        f"- Project: `{config.project_name}`",
        f"- Environment: `{config.environment}`",
        f"- Endpoint: `{config.endpoint_name}`",
        f"- Model Package Group: `{config.model_package_group_name}`",
        "",
        "## Executive Summary",
        "",
        "This report aggregates local metadata produced by the lab commands. Missing sections indicate commands not executed yet.",
        "",
    ]
    for title, metadata_name in SECTIONS:
        data = read_metadata(config, metadata_name)
        lines.extend([f"## {title}", ""])
        if data:
            lines.extend(["```json", json.dumps(data, indent=2, default=str), "```", ""])
        else:
            lines.extend(["Not available yet.", ""])

    lines.extend(
        [
            "## Recommended Decision",
            "",
            "Use monitoring evidence to choose retraining, rollback, baseline update, human review, or no action. Retraining is disabled by default.",
            "",
            "## Cost Warnings",
            "",
            "- SageMaker endpoints generate cost while active.",
            "- Training, processing and Model Monitor jobs generate cost during execution.",
            "- CloudWatch Logs, S3, Lambda and Step Functions can generate cost.",
            "",
            "## Cleanup Steps",
            "",
            "Run explicit cleanup targets when finished:",
            "",
            "```bash",
            "make destroy-endpoint",
            "make destroy-monitoring",
            "make destroy-feedback-loop",
            "make destroy-all",
            "```",
            "",
            "## MLOps Readiness Checklist",
            "",
            "- Data generated or integrated.",
            "- Build pipeline created.",
            "- Model Registry populated.",
            "- Approval gate used.",
            "- Deployment controlled.",
            "- Data Capture enabled.",
            "- Baseline and monitoring schedule created.",
            "- Native Model Quality Monitor configured with predictions, InferenceId, and delayed labels.",
            "- CloudWatch alarm and EventBridge rule configured.",
            "- Step Functions feedback loop configured.",
            "- Optional Batch Transform monitoring evidence captured when step 12 is executed.",
            "- Cleanup documented.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(path)
    return path


if __name__ == "__main__":
    generate_report()
