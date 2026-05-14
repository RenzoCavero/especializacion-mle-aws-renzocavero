from __future__ import annotations

import logging
import tarfile
from pathlib import Path
from botocore.exceptions import ClientError

from src.aws_clients import client, sklearn_image_uri, upload_file
from src.config import PROJECT_ROOT, get_config, s3_join
from src.logging_utils import configure_logging
from src.state import load_state, update_state


LOGGER = logging.getLogger(__name__)


LAB_TAGS = [
    {"Key": "Project", "Value": "MLModelTrainingOptimization"},
    {"Key": "Environment", "Value": "Lab"},
    {"Key": "ManagedBy", "Value": "Scripts"},
]


def ensure_model_package_group(config) -> None:
    sm = client(config, "sagemaker")
    try:
        sm.describe_model_package_group(ModelPackageGroupName=config.model_package_group_name)
        return
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"ResourceNotFound", "ValidationException"}:
            raise
    sm.create_model_package_group(
        ModelPackageGroupName=config.model_package_group_name,
        ModelPackageGroupDescription="Churn model package group for AWS ML training optimization lab.",
        Tags=LAB_TAGS,
    )
    LOGGER.info("Created Model Package Group %s", config.model_package_group_name)


def package_inference_source(config) -> str:
    archive_path = config.local_outputs_dir / "inference_source.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(PROJECT_ROOT / "training" / "inference.py", arcname="inference.py")
    s3_uri = s3_join(config.s3_bucket_name, "code", "inference_source.tar.gz")
    upload_file(config, str(archive_path), s3_uri)
    return s3_uri


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    state = load_state()
    model_artifact = (
        state.get("selected_model_artifact_s3_uri")
        or state.get("best_model_artifact_s3_uri")
        or state.get("baseline_model_artifact_s3_uri")
    )
    if not model_artifact:
        raise ValueError("No selected model artifact found. Run training, HPO and compare-models first.")
    metrics_s3_uri = state.get("selected_metrics_s3_uri") or state.get("optimized_metrics_s3_uri") or state.get("baseline_metrics_s3_uri")
    if not metrics_s3_uri:
        raise ValueError("No model metrics S3 URI found. Run evaluation first.")

    ensure_model_package_group(config)
    inference_source_s3_uri = package_inference_source(config)
    sm = client(config, "sagemaker")
    response = sm.create_model_package(
        ModelPackageGroupName=config.model_package_group_name,
        ModelPackageDescription="Best churn model from lab 03 training and HPO.",
        ModelApprovalStatus="PendingManualApproval",
        InferenceSpecification={
            "Containers": [
                {
                    "Image": sklearn_image_uri(config),
                    "ModelDataUrl": model_artifact,
                    "Environment": {
                        "SAGEMAKER_PROGRAM": "inference.py",
                        "SAGEMAKER_SUBMIT_DIRECTORY": inference_source_s3_uri,
                        "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
                        "SAGEMAKER_REGION": config.aws_region,
                    },
                }
            ],
            "SupportedContentTypes": ["text/csv", "application/json"],
            "SupportedResponseMIMETypes": ["text/csv", "application/json"],
            "SupportedRealtimeInferenceInstanceTypes": ["ml.m5.large"],
            "SupportedTransformInstanceTypes": ["ml.m5.large"],
        },
        ModelMetrics={
            "ModelQuality": {
                "Statistics": {
                    "ContentType": "application/json",
                    "S3Uri": metrics_s3_uri,
                }
            }
        },
        CustomerMetadataProperties={
            "feature_group_name": config.feature_group_name,
            "record_identifier": "customer_id",
            "event_time_feature": "event_time",
            "objective_metric": state.get("objective_metric_name", "f1"),
            "objective_metric_value": str(state.get("objective_metric_value", "")),
            "dataset_s3_uri": state.get("train_s3_uri", config.train_s3_uri),
            "offline_store_s3_uri": config.offline_store_s3_uri,
            "online_store_enabled": str(config.enable_online_store),
            "batch_inference_source": "offline_store",
            "realtime_lookup_key": "customer_id",
        },
    )
    model_package_arn = response["ModelPackageArn"]
    update_state(
        model_package_arn=model_package_arn,
        model_package_group_name=config.model_package_group_name,
        model_approval_status="PendingManualApproval",
        inference_source_s3_uri=inference_source_s3_uri,
    )
    LOGGER.info("Registered model package: %s", model_package_arn)


if __name__ == "__main__":
    main()
