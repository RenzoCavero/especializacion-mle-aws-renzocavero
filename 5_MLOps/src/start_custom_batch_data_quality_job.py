"""Run the custom Data Quality evaluator for Batch Transform inputs."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata
from .custom_data_quality_job import (
    custom_data_quality_job_name,
    custom_data_quality_processing_request,
    select_custom_data_quality_compute,
    upload_custom_data_quality_code,
    wait_for_processing_job,
)
from .custom_model_quality_job import sklearn_processing_image_uri


def start_custom_batch_data_quality_job(
    *,
    wait: bool = False,
    poll_seconds: int = 30,
    timeout_seconds: int = 2400,
    current_data_s3_uri: str = "",
    if_native_unavailable: bool = False,
) -> dict[str, object]:
    config = load_config(validate=True, require_execution_role=True)
    if if_native_unavailable:
        native_metadata = read_metadata(config, "batch_monitoring_schedule")
        native_status = str(native_metadata.get("status") or "")
        if native_status != "native_batch_schedule_unavailable":
            payload = {
                "skipped": True,
                "reason": "native_batch_monitoring_schedule_available",
                "native_status": native_status or "unknown",
            }
            write_metadata(config, "custom_batch_data_quality_job", payload)
            return payload

    clients = create_clients(config)
    processing_compute = select_custom_data_quality_compute(clients, config)
    code_s3_uri = upload_custom_data_quality_code(clients, config, code_s3_uri=config.custom_batch_data_quality_code_s3_uri)
    image_uri = sklearn_processing_image_uri(config)
    job_name = custom_data_quality_job_name(config, job_prefix="custom-batch-data-quality")
    source_s3_uri = current_data_s3_uri or config.batch_transform_input_s3_uri
    request = custom_data_quality_processing_request(
        config=config,
        job_name=job_name,
        image_uri=image_uri,
        instance_type=processing_compute.selected_instance_type,
        code_s3_uri=code_s3_uri,
        baseline_data_s3_uri=config.baseline_monitor_s3_uri,
        current_data_s3_uri=source_s3_uri,
        data_capture_s3_uri=config.batch_data_capture_s3_uri,
        reports_s3_uri=config.custom_batch_data_quality_reports_s3_uri,
        metric_name=config.batch_violations_metric_name,
        metric_dimension_name="BatchMonitoringSchedule",
        metric_dimension_value=config.batch_monitoring_schedule_name,
        endpoint_name=config.sagemaker_batch_model_name,
        window_hours=config.custom_data_quality_window_hours,
    )
    response = clients.sagemaker.create_processing_job(**request)

    description: dict[str, object] = {}
    if wait:
        print(
            "Custom Batch Data Quality Processing Job started: "
            f"{job_name} on {processing_compute.selected_instance_type}. "
            f"Local wait timeout: {timeout_seconds}s."
        )
        description = wait_for_processing_job(clients, job_name, poll_seconds, timeout_seconds)
        if description.get("ProcessingJobStatus") != "Completed":
            raise RuntimeError(
                f"Custom Batch Data Quality job {job_name} ended with status "
                f"{description.get('ProcessingJobStatus')}: {description.get('FailureReason', '')}"
            )

    payload = {
        "job_name": job_name,
        "processing_job_arn": response.get("ProcessingJobArn", ""),
        "status": description.get("ProcessingJobStatus", "Started") if description else "Started",
        "mode": "manual",
        "image_uri": image_uri,
        "code_s3_uri": code_s3_uri,
        "baseline_data_s3_uri": config.baseline_monitor_s3_uri,
        "current_data_s3_uri": source_s3_uri,
        "batch_data_capture_s3_uri": config.batch_data_capture_s3_uri,
        "reports_s3_uri": config.custom_batch_data_quality_reports_s3_uri,
        "custom_metric": {
            "namespace": config.metric_namespace,
            "metric_name": config.batch_violations_metric_name,
            "dimension": {"BatchMonitoringSchedule": config.batch_monitoring_schedule_name},
        },
        "compute_selection": processing_compute.to_dict(),
        "processing_job_description": description,
    }
    write_metadata(config, "custom_batch_data_quality_job", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=int, default=2400)
    parser.add_argument("--current-data-s3-uri", default="")
    parser.add_argument("--if-native-unavailable", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            start_custom_batch_data_quality_job(
                wait=args.wait,
                poll_seconds=args.poll_seconds,
                timeout_seconds=args.timeout_seconds,
                current_data_s3_uri=args.current_data_s3_uri,
                if_native_unavailable=args.if_native_unavailable,
            ),
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
