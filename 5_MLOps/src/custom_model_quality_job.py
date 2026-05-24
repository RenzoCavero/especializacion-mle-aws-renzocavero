"""Shared helpers for the custom Model Quality Processing Job fallback."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .compute import select_instance_type
from .config import LabConfig


FRAMEWORK_VERSION = "1.2-1"
PYTHON_VERSION = "py3"


def sklearn_processing_image_uri(config: LabConfig) -> str:
    if config.model_image_uri:
        return config.model_image_uri
    framework_accounts = {
        "af-south-1": "626614931356",
        "ap-east-1": "871362719292",
        "ap-northeast-1": "354813040037",
        "ap-northeast-2": "366743142698",
        "ap-south-1": "720646828776",
        "ap-southeast-1": "121021644041",
        "ap-southeast-2": "783357654285",
        "ca-central-1": "341280168497",
        "eu-central-1": "492215442770",
        "eu-north-1": "662702820516",
        "eu-south-1": "692866216735",
        "eu-west-1": "141502667606",
        "eu-west-2": "764974769150",
        "eu-west-3": "659782779980",
        "me-south-1": "217643126080",
        "sa-east-1": "737474898029",
        "us-east-1": "683313688378",
        "us-east-2": "257758044811",
        "us-west-1": "746614075791",
        "us-west-2": "246618743249",
    }
    account_id = framework_accounts.get(config.aws_region)
    if not account_id:
        raise ValueError(
            "Could not resolve the SageMaker scikit-learn image for this region. "
            "Set MODEL_IMAGE_URI in .env."
        )
    return (
        f"{account_id}.dkr.ecr.{config.aws_region}.amazonaws.com/"
        f"sagemaker-scikit-learn:{FRAMEWORK_VERSION}-cpu-{PYTHON_VERSION}"
    )


def custom_model_quality_job_name(config: LabConfig) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{config.resource_prefix}-custom-model-quality-{timestamp}"[:63].strip("-")


def upload_custom_model_quality_code(clients, config: LabConfig) -> str:
    source = Path("processing/custom_model_quality.py")
    if not source.exists():
        raise FileNotFoundError(f"Missing custom processor source: {source}")
    bucket, key_prefix = _parse_s3_uri(config.custom_model_quality_code_s3_uri)
    clients.s3.upload_file(str(source), bucket, f"{key_prefix}/custom_model_quality.py")
    return config.custom_model_quality_code_s3_uri


def select_custom_model_quality_compute(clients, config: LabConfig):
    processing_compute = select_instance_type(
        config,
        workload="processing",
        preferred=config.model_monitor_processing_instance_type,
        candidates=config.model_monitor_processing_instance_type_candidates_list,
        session=clients.session,
    )
    if processing_compute.source == "fallback-no-positive-quota":
        raise RuntimeError("No SageMaker processing quota is available for custom Model Quality jobs.")
    return processing_compute


def custom_model_quality_environment(
    config: LabConfig,
    *,
    predictions_s3_uri: str = "",
    ground_truth_debug_s3_uri: str = "",
    window_hours: int | None = None,
) -> dict[str, str]:
    return {
        "AWS_REGION": config.aws_region,
        "ENDPOINT_NAME": config.endpoint_name,
        "PREDICTIONS_S3_URI": predictions_s3_uri or config.model_quality_predictions_s3_uri,
        "GROUND_TRUTH_DEBUG_S3_URI": ground_truth_debug_s3_uri or config.model_quality_ground_truth_debug_s3_uri,
        "METRIC_NAMESPACE": config.metric_namespace,
        "MODEL_QUALITY_RECORDS_METRIC_NAME": config.model_quality_records_metric_name,
        "MODEL_QUALITY_ACCURACY_METRIC_NAME": config.model_quality_accuracy_metric_name,
        "MODEL_QUALITY_F1_METRIC_NAME": config.model_quality_f1_metric_name,
        "MODEL_QUALITY_AUC_METRIC_NAME": config.model_quality_auc_metric_name,
        "MODEL_QUALITY_ACCURACY_THRESHOLD": str(config.model_quality_accuracy_threshold),
        "MODEL_QUALITY_F1_THRESHOLD": str(config.model_quality_f1_threshold),
        "MODEL_QUALITY_AUC_THRESHOLD": str(config.model_quality_auc_threshold),
        "MODEL_QUALITY_MIN_RECORDS": str(config.model_quality_min_records),
        "CUSTOM_MODEL_QUALITY_WINDOW_HOURS": str(
            config.custom_model_quality_window_hours if window_hours is None else window_hours
        ),
    }


def custom_model_quality_processing_request(
    *,
    config: LabConfig,
    job_name: str,
    image_uri: str,
    instance_type: str,
    code_s3_uri: str,
    predictions_s3_uri: str = "",
    ground_truth_debug_s3_uri: str = "",
    window_hours: int | None = None,
) -> dict[str, Any]:
    return {
        "ProcessingJobName": job_name,
        "RoleArn": config.sagemaker_execution_role_arn,
        "AppSpecification": {
            "ImageUri": image_uri,
            "ContainerEntrypoint": ["python3", "/opt/ml/processing/code/custom_model_quality.py"],
        },
        "Environment": custom_model_quality_environment(
            config,
            predictions_s3_uri=predictions_s3_uri,
            ground_truth_debug_s3_uri=ground_truth_debug_s3_uri,
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
                "InputName": "custom-model-quality-code",
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
                    "OutputName": "custom-model-quality-report",
                    "S3Output": {
                        "S3Uri": config.custom_model_quality_reports_s3_uri,
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
        print(f"Custom Model Quality job status: {status}. Waiting {poll_seconds}s...")
        time.sleep(poll_seconds)


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    bucket_key = uri[5:]
    bucket, _, key = bucket_key.partition("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI without bucket/key: {uri}")
    return bucket, key.rstrip("/")
