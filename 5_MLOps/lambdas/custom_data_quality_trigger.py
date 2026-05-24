"""Start the custom Data Quality Processing Job from EventBridge."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import boto3


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _job_name() -> str:
    prefix = _env("JOB_PREFIX", "mlops-custom-data-quality")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}"[:63].strip("-")


def _processing_environment() -> dict[str, str]:
    names = [
        "AWS_REGION",
        "ENDPOINT_NAME",
        "BASELINE_DATA_S3_URI",
        "CURRENT_DATA_S3_URI",
        "DATA_CAPTURE_S3_URI",
        "METRIC_NAMESPACE",
        "VIOLATIONS_METRIC_NAME",
        "METRIC_DIMENSION_NAME",
        "METRIC_DIMENSION_VALUE",
        "CUSTOM_DATA_QUALITY_WINDOW_HOURS",
    ]
    return {name: _env(name) for name in names if _env(name)}


def handler(event, context):
    sagemaker = boto3.client("sagemaker", region_name=_env("AWS_REGION"))
    job_name = _job_name()
    response = sagemaker.create_processing_job(
        ProcessingJobName=job_name,
        RoleArn=_env("SAGEMAKER_EXECUTION_ROLE_ARN"),
        AppSpecification={
            "ImageUri": _env("PROCESSING_IMAGE_URI"),
            "ContainerEntrypoint": ["python3", "/opt/ml/processing/code/custom_data_quality.py"],
        },
        Environment=_processing_environment(),
        ProcessingResources={
            "ClusterConfig": {
                "InstanceCount": 1,
                "InstanceType": _env("PROCESSING_INSTANCE_TYPE", "ml.m6i.large"),
                "VolumeSizeInGB": int(_env("PROCESSING_VOLUME_SIZE_GB", "20")),
            }
        },
        ProcessingInputs=[
            {
                "InputName": "custom-data-quality-code",
                "S3Input": {
                    "S3Uri": _env("CODE_S3_URI"),
                    "LocalPath": "/opt/ml/processing/code",
                    "S3DataType": "S3Prefix",
                    "S3InputMode": "File",
                    "S3DataDistributionType": "FullyReplicated",
                    "S3CompressionType": "None",
                },
            }
        ],
        ProcessingOutputConfig={
            "Outputs": [
                {
                    "OutputName": "custom-data-quality-report",
                    "S3Output": {
                        "S3Uri": _env("REPORTS_S3_URI"),
                        "LocalPath": "/opt/ml/processing/output",
                        "S3UploadMode": "EndOfJob",
                    },
                }
            ]
        },
        StoppingCondition={"MaxRuntimeInSeconds": int(_env("MAX_RUNTIME_SECONDS", "1800"))},
    )
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "job_name": job_name,
                "processing_job_arn": response.get("ProcessingJobArn", ""),
                "trigger_event": event,
            },
            default=str,
        ),
    }
