"""Simulate data quality drift and run the custom fallback evaluator."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata
from .simulate_drift import send_drift
from .start_custom_data_quality_job import start_custom_data_quality_job


def _ensure_drift_s3_uri(config) -> str:
    metadata = read_metadata(config, "data_generation")
    s3_files = metadata.get("s3_files", {}) if isinstance(metadata, dict) else {}
    drift_uri = str(s3_files.get("inference_drift") or "")
    if drift_uri:
        return drift_uri

    local_drift = config.local_cache_dir / "inference_drift.jsonl"
    if not local_drift.exists():
        raise FileNotFoundError("Missing data/local_cache/inference_drift.jsonl. Run step 02 first.")
    clients = create_clients(config)
    key = f"{config.resource_prefix}/{config.environment}/data/raw/inference_drift.jsonl"
    clients.s3.upload_file(str(local_drift), config.s3_bucket_name, key)
    return f"s3://{config.s3_bucket_name}/{key}"


def simulate_data_quality_alarm(
    limit: int = 50,
    wait: bool = False,
    poll_seconds: int = 30,
    timeout_seconds: int = 2400,
) -> dict[str, object]:
    config = load_config(validate=True)
    drift = send_drift(limit=limit)
    current_data_s3_uri = _ensure_drift_s3_uri(config)
    job = start_custom_data_quality_job(
        wait=wait,
        poll_seconds=poll_seconds,
        timeout_seconds=timeout_seconds,
        current_data_s3_uri=current_data_s3_uri,
        baseline_data_s3_uri=config.baseline_monitor_s3_uri,
    )
    alarm_metadata = read_metadata(config, "cloudwatch_alarm")
    payload = {
        "scenario": "data_quality_alarm",
        "intent": "Drifted input records are compared against the data quality baseline to force violations.",
        "drift_traffic": drift,
        "custom_data_quality_job": job,
        "expected_alarm": alarm_metadata.get("alarm_name") or config.custom_data_quality_alarm_name,
        "expected_metric": {
            "namespace": config.metric_namespace,
            "metric_name": config.violations_metric_name,
            "dimension": {"EndpointName": config.endpoint_name},
            "comparison": f">= {config.alarm_threshold}",
        },
        "next_steps": [
            "Ensure python -m src.create_cloudwatch_alarm was executed.",
            "Ensure python -m src.create_alarm_notifications and python -m src.create_eventbridge_rule were executed.",
            "Confirm the SNS subscription email before expecting email delivery.",
        ],
    }
    write_metadata(config, "data_quality_alarm_simulation", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=int, default=2400)
    args = parser.parse_args()
    print(
        json.dumps(
            simulate_data_quality_alarm(
                limit=args.limit,
                wait=args.wait,
                poll_seconds=args.poll_seconds,
                timeout_seconds=args.timeout_seconds,
            ),
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
