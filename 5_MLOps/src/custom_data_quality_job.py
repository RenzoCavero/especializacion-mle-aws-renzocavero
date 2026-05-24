"""Shared helpers for the custom Data Quality Processing Job fallback."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .compute import select_instance_type
from .config import LabConfig
from .custom_model_quality_job import _parse_s3_uri, sklearn_processing_image_uri


def custom_data_quality_job_name(config: LabConfig, *, job_prefix: str = "custom-data-quality") -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{config.resource_prefix}-{job_prefix}-{timestamp}"[:63].strip("-")


def upload_custom_data_quality_code(clients, config: LabConfig, *, code_s3_uri: str = "") -> str:
    source = Path("processing/custom_data_quality.py")
    if not source.exists():
        raise FileNotFoundError(f"Missing custom processor source: {source}")
    target_uri = code_s3_uri or config.custom_data_quality_code_s3_uri
    bucket, key_prefix = _parse_s3_uri(target_uri)
    clients.s3.upload_file(str(source), bucket, f"{key_prefix}/custom_data_quality.py")
    return target_uri


def select_custom_data_quality_compute(clients, config: LabConfig):
    processing_compute = select_instance_type(
        config,
        workload="processing",
        preferred=config.model_monitor_processing_instance_type,
        candidates=config.model_monitor_processing_instance_type_candidates_list,
        session=clients.session,
    )
    if processing_compute.source == "fallback-no-positive-quota":
        raise RuntimeError("No SageMaker processing quota is available for custom Data Quality jobs.")
    return processing_compute


def custom_data_quality_environment(
    config: LabConfig,
    *,
    baseline_data_s3_uri: str = "",
    current_data_s3_uri: str = "",
    data_capture_s3_uri: str = "",
    metric_name: str = "",
    metric_dimension_name: str = "",
    metric_dimension_value: str = "",
    endpoint_name: str = "",
    window_hours: int | None = None,
) -> dict[str, str]:
    environment = {
        "AWS_REGION": config.aws_region,
        "ENDPOINT_NAME": endpoint_name or config.endpoint_name,
        "BASELINE_DATA_S3_URI": baseline_data_s3_uri or config.baseline_monitor_s3_uri,
        "CURRENT_DATA_S3_URI": current_data_s3_uri,
        "DATA_CAPTURE_S3_URI": data_capture_s3_uri or config.data_capture_s3_uri,
        "METRIC_NAMESPACE": config.metric_namespace,
        "VIOLATIONS_METRIC_NAME": metric_name or config.violations_metric_name,
        "METRIC_DIMENSION_NAME": metric_dimension_name,
        "METRIC_DIMENSION_VALUE": metric_dimension_value,
        "CUSTOM_DATA_QUALITY_WINDOW_HOURS": str(
            config.custom_data_quality_window_hours if window_hours is None else window_hours
        ),
    }
    return {key: value for key, value in environment.items() if value}


def custom_data_quality_processing_request(
    *,
    config: LabConfig,
    job_name: str,
    image_uri: str,
    instance_type: str,
    code_s3_uri: str,
    baseline_data_s3_uri: str = "",
    current_data_s3_uri: str = "",
    data_capture_s3_uri: str = "",
    reports_s3_uri: str = "",
    metric_name: str = "",
    metric_dimension_name: str = "",
    metric_dimension_value: str = "",
    endpoint_name: str = "",
    window_hours: int | None = None,
) -> dict[str, Any]:
    return {
        "ProcessingJobName": job_name,
        "RoleArn": config.sagemaker_execution_role_arn,
        "AppSpecification": {
            "ImageUri": image_uri,
            "ContainerEntrypoint": ["python3", "/opt/ml/processing/code/custom_data_quality.py"],
        },
        "Environment": custom_data_quality_environment(
            config,
            baseline_data_s3_uri=baseline_data_s3_uri,
            current_data_s3_uri=current_data_s3_uri,
            data_capture_s3_uri=data_capture_s3_uri,
            metric_name=metric_name,
            metric_dimension_name=metric_dimension_name,
            metric_dimension_value=metric_dimension_value,
            endpoint_name=endpoint_name,
            window_hours=window_hours,
        ),
        "ProcessingResources": {
            "ClusterConfig": {
                "InstanceCount": 1,
                "InstanceType": instance_type,
                "VolumeSizeInGB": 20,
            }
        },
        "ProcessingInputs": [
            {
                "InputName": "custom-data-quality-code",
                "S3Input": {
                    "S3Uri": code_s3_uri,
                    "LocalPath": "/opt/ml/processing/code",
                    "S3DataType": "S3Prefix",
                    "S3InputMode": "File",
                    "S3DataDistributionType": "FullyReplicated",
                    "S3CompressionType": "None",
                },
            }
        ],
        "ProcessingOutputConfig": {
            "Outputs": [
                {
                    "OutputName": "custom-data-quality-report",
                    "S3Output": {
                        "S3Uri": reports_s3_uri or config.custom_data_quality_reports_s3_uri,
                        "LocalPath": "/opt/ml/processing/output",
                        "S3UploadMode": "EndOfJob",
                    },
                }
            ]
        },
        "StoppingCondition": {"MaxRuntimeInSeconds": 1800},
        "Tags": config.tags,
    }


def wait_for_processing_job(clients, job_name: str, poll_seconds: int, timeout_seconds: int) -> dict[str, Any]:
    started_at = time.monotonic()
    while True:
        description = clients.sagemaker.describe_processing_job(ProcessingJobName=job_name)
        status = str(description.get("ProcessingJobStatus"))
        if status in {"Completed", "Failed", "Stopped"}:
            return description
        elapsed_seconds = int(time.monotonic() - started_at)
        if timeout_seconds > 0 and elapsed_seconds >= timeout_seconds:
            raise TimeoutError(f"Processing job {job_name} is still {status} after {elapsed_seconds}s.")
        print(f"Custom Data Quality job status: {status}. Waiting {poll_seconds}s...")
        time.sleep(poll_seconds)
