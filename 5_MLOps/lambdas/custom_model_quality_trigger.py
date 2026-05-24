"""Start the custom Model Quality Processing Job from EventBridge."""

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
    prefix = _env("JOB_PREFIX", "mlops-custom-model-quality")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}"[:63].strip("-")


def _processing_environment() -> dict[str, str]:
    names = [
        "AWS_REGION",
        "ENDPOINT_NAME",
        "PREDICTIONS_S3_URI",
        "GROUND_TRUTH_DEBUG_S3_URI",
        "METRIC_NAMESPACE",
        "MODEL_QUALITY_RECORDS_METRIC_NAME",
        "MODEL_QUALITY_ACCURACY_METRIC_NAME",
        "MODEL_QUALITY_F1_METRIC_NAME",
        "MODEL_QUALITY_AUC_METRIC_NAME",
        "MODEL_QUALITY_ACCURACY_THRESHOLD",
        "MODEL_QUALITY_F1_THRESHOLD",
        "MODEL_QUALITY_AUC_THRESHOLD",
        "MODEL_QUALITY_MIN_RECORDS",
        "CUSTOM_MODEL_QUALITY_WINDOW_HOURS",
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
            "ContainerEntrypoint": ["python3", "/opt/ml/processing/code/custom_model_quality.py"],
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
                "InputName": "custom-model-quality-code",
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
                    "OutputName": "custom-model-quality-report",
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
