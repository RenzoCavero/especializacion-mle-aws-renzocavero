"""Start the custom Model Quality Processing Job manually."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, write_metadata
from .custom_model_quality_job import (
    custom_model_quality_job_name,
    custom_model_quality_processing_request,
    select_custom_model_quality_compute,
    sklearn_processing_image_uri,
    upload_custom_model_quality_code,
    wait_for_processing_job,
)


def start_custom_model_quality_job(
    wait: bool = False,
    poll_seconds: int = 30,
    timeout_seconds: int = 2400,
    predictions_s3_uri: str = "",
    ground_truth_debug_s3_uri: str = "",
    window_hours: int | None = None,
) -> dict[str, object]:
    config = load_config(validate=True, require_execution_role=True)
    clients = create_clients(config)
    processing_compute = select_custom_model_quality_compute(clients, config)
    code_s3_uri = upload_custom_model_quality_code(clients, config)
    image_uri = sklearn_processing_image_uri(config)
    job_name = custom_model_quality_job_name(config)
    request = custom_model_quality_processing_request(
        config=config,
        job_name=job_name,
        image_uri=image_uri,
        instance_type=processing_compute.selected_instance_type,
        code_s3_uri=code_s3_uri,
        predictions_s3_uri=predictions_s3_uri,
        ground_truth_debug_s3_uri=ground_truth_debug_s3_uri,
        window_hours=window_hours,
    )
    response = clients.sagemaker.create_processing_job(**request)
    description: dict[str, object] = {}
    if wait:
        print(
            "Custom Model Quality Processing Job started: "
            f"{job_name} on {processing_compute.selected_instance_type}. "
            f"Local wait timeout: {timeout_seconds}s."
        )
        description = wait_for_processing_job(clients, job_name, poll_seconds, timeout_seconds)
        if description.get("ProcessingJobStatus") != "Completed":
            raise RuntimeError(
                f"Custom Model Quality job {job_name} ended with status "
                f"{description.get('ProcessingJobStatus')}: {description.get('FailureReason', '')}"
            )
    payload = {
        "job_name": job_name,
        "processing_job_arn": response.get("ProcessingJobArn", ""),
        "status": "started" if not wait else str(description.get("ProcessingJobStatus")),
        "mode": "manual",
        "image_uri": image_uri,
        "code_s3_uri": code_s3_uri,
        "predictions_s3_uri": predictions_s3_uri or config.model_quality_predictions_s3_uri,
        "ground_truth_debug_s3_uri": ground_truth_debug_s3_uri or config.model_quality_ground_truth_debug_s3_uri,
        "reports_s3_uri": config.custom_model_quality_reports_s3_uri,
        "input_scope": "explicit_run_objects" if predictions_s3_uri or ground_truth_debug_s3_uri else "configured_window",
        "window_hours": config.custom_model_quality_window_hours if window_hours is None else window_hours,
        "custom_metric": {
            "namespace": config.metric_namespace,
            "f1_metric_name": config.model_quality_f1_metric_name,
            "dimension": {"EndpointName": config.endpoint_name},
        },
        "compute_selection": processing_compute.to_dict(),
        "processing_job_description": description,
    }
    write_metadata(config, "custom_model_quality_job", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=int, default=2400)
    parser.add_argument("--predictions-s3-uri", default="")
    parser.add_argument("--ground-truth-debug-s3-uri", default="")
    parser.add_argument("--window-hours", type=int, default=None)
    args = parser.parse_args()
    print(
        json.dumps(
            start_custom_model_quality_job(
                wait=args.wait,
                poll_seconds=args.poll_seconds,
                timeout_seconds=args.timeout_seconds,
                predictions_s3_uri=args.predictions_s3_uri,
                ground_truth_debug_s3_uri=args.ground_truth_debug_s3_uri,
                window_hours=args.window_hours,
            ),
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
