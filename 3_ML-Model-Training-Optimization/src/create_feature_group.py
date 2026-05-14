from __future__ import annotations

import logging
import time
from botocore.exceptions import ClientError

from src.aws_clients import client
from src.config import get_config
from src.feature_schema import (
    EVENT_TIME_FEATURE_NAME,
    RECORD_IDENTIFIER_NAME,
    sagemaker_feature_definitions,
)
from src.logging_utils import configure_logging
from src.state import update_state


LOGGER = logging.getLogger(__name__)


def wait_for_feature_group(config, timeout_seconds: int = 900) -> dict:
    sm = client(config, "sagemaker")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = sm.describe_feature_group(FeatureGroupName=config.feature_group_name)
        status = response.get("FeatureGroupStatus")
        LOGGER.info("Feature Group %s status: %s", config.feature_group_name, status)
        if status == "Created":
            return response
        if status in {"CreateFailed", "DeleteFailed"}:
            raise RuntimeError(f"Feature Group entered terminal status {status}: {response}")
        time.sleep(20)
    raise TimeoutError(f"Timed out waiting for Feature Group {config.feature_group_name}")


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    sm = client(config, "sagemaker")

    try:
        response = sm.describe_feature_group(FeatureGroupName=config.feature_group_name)
        LOGGER.info("Feature Group already exists: %s", response.get("FeatureGroupStatus"))
        if response.get("FeatureGroupStatus") != "Created":
            response = wait_for_feature_group(config)
        update_state(feature_group_name=config.feature_group_name)
        return
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"ResourceNotFound", "ValidationException"}:
            raise

    create_args = {
        "FeatureGroupName": config.feature_group_name,
        "RecordIdentifierFeatureName": RECORD_IDENTIFIER_NAME,
        "EventTimeFeatureName": EVENT_TIME_FEATURE_NAME,
        "FeatureDefinitions": sagemaker_feature_definitions(),
        "RoleArn": config.sagemaker_execution_role_arn,
        "Tags": [
            {"Key": "Project", "Value": "MLModelTrainingOptimization"},
            {"Key": "Environment", "Value": "Lab"},
            {"Key": "Owner", "Value": "Student"},
            {"Key": "ManagedBy", "Value": "Scripts"},
            {"Key": "CostCenter", "Value": "Training"},
            {"Key": "AutoDelete", "Value": "true"},
        ],
    }
    if config.enable_online_store:
        create_args["OnlineStoreConfig"] = {"EnableOnlineStore": True}
    if config.enable_offline_store:
        s3_storage_config = {"S3Uri": config.offline_store_s3_uri}
        if config.kms_key_arn:
            s3_storage_config["KmsKeyId"] = config.kms_key_arn
        create_args["OfflineStoreConfig"] = {
            "S3StorageConfig": s3_storage_config,
            "DisableGlueTableCreation": False,
        }

    LOGGER.info("Creating Feature Group %s", config.feature_group_name)
    sm.create_feature_group(**create_args)
    response = wait_for_feature_group(config)
    update_state(
        feature_group_name=config.feature_group_name,
        offline_store_s3_uri=config.offline_store_s3_uri,
        feature_group_arn=response.get("FeatureGroupArn"),
    )


if __name__ == "__main__":
    main()
