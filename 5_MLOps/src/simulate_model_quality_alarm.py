"""Simulate poor model quality and run the custom fallback evaluator."""

from __future__ import annotations

import argparse
import json

from .capture_model_quality_data import capture_model_quality_data
from .config import load_config, write_metadata
from .start_custom_model_quality_job import start_custom_model_quality_job
from .validate_model_quality_endpoint import validate_model_quality_endpoint


def simulate_model_quality_alarm(
    limit: int = 50,
    wait: bool = False,
    poll_seconds: int = 30,
    timeout_seconds: int = 2400,
) -> dict[str, object]:
    config = load_config(validate=True)
    endpoint_validation = validate_model_quality_endpoint()
    capture = capture_model_quality_data(
        traffic_type="normal",
        limit=limit,
        label_mode="opposite-prediction",
    )
    job = start_custom_model_quality_job(
        wait=wait,
        poll_seconds=poll_seconds,
        timeout_seconds=timeout_seconds,
        predictions_s3_uri=str(capture.get("predictions_s3_uri") or ""),
        ground_truth_debug_s3_uri=str(capture.get("ground_truth_debug_s3_uri") or ""),
    )
    payload = {
        "scenario": "model_quality_alarm",
        "intent": "Ground truth labels are set to the opposite of endpoint predictions to force a low F1 score.",
        "endpoint_validation": endpoint_validation,
        "capture": capture,
        "custom_model_quality_job": job,
        "expected_alarm": config.custom_model_quality_alarm_name,
        "expected_metric": {
            "namespace": config.metric_namespace,
            "metric_name": config.model_quality_f1_metric_name,
            "dimension": {"EndpointName": config.endpoint_name},
            "comparison": f"< {config.model_quality_f1_threshold}",
        },
        "next_steps": [
            "Ensure python -m src.create_custom_model_quality_alarm was executed.",
            "Ensure python -m src.create_alarm_notifications and python -m src.create_eventbridge_rule were executed.",
            "Confirm the SNS subscription email before expecting email delivery.",
        ],
    }
    write_metadata(config, "model_quality_alarm_simulation", payload)
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
            simulate_model_quality_alarm(
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
