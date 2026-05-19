from __future__ import annotations

import argparse
import json
import logging
import re
from botocore.exceptions import ClientError

from src.aws_clients import client
from src.config import get_config
from src.logging_utils import configure_logging
from src.state import load_state, update_state


LOGGER = logging.getLogger(__name__)


LAB_TAGS = [
    {"Key": "Project", "Value": "MLModelTrainingOptimization"},
    {"Key": "Environment", "Value": "Lab"},
    {"Key": "ManagedBy", "Value": "Scripts"},
]


def latest_model_package_arn(sm, model_package_group_name: str) -> str:
    response = sm.list_model_packages(
        ModelPackageGroupName=model_package_group_name,
        SortBy="CreationTime",
        SortOrder="Descending",
        MaxResults=1,
    )
    packages = response.get("ModelPackageSummaryList", [])
    if not packages:
        raise ValueError(
            f"No model packages found in group {model_package_group_name}. "
            "Run python -m src.register_model first."
        )
    return packages[0]["ModelPackageArn"]


def version_from_model_package_arn(model_package_arn: str) -> str:
    version = model_package_arn.rstrip("/").split("/")[-1]
    if not version:
        return "latest"
    return re.sub(r"[^A-Za-z0-9-]", "-", version)


def default_deployable_model_name(resource_prefix: str, model_package_arn: str) -> str:
    version = version_from_model_package_arn(model_package_arn)
    name = f"{resource_prefix}-deployable-v{version}"
    return name[:63].rstrip("-")


def approve_model_package(sm, model_package_arn: str) -> dict:
    sm.update_model_package(
        ModelPackageArn=model_package_arn,
        ModelApprovalStatus="Approved",
    )
    return sm.describe_model_package(ModelPackageName=model_package_arn)


def create_deployable_model(sm, *, model_name: str, model_package_arn: str, execution_role_arn: str) -> str:
    try:
        response = sm.describe_model(ModelName=model_name)
        LOGGER.info("SageMaker Model already exists: %s", model_name)
        return response["ModelArn"]
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"ValidationException", "ResourceNotFound"}:
            raise

    response = sm.create_model(
        ModelName=model_name,
        ExecutionRoleArn=execution_role_arn,
        PrimaryContainer={"ModelPackageName": model_package_arn},
        Tags=LAB_TAGS,
    )
    LOGGER.info("Created deployable SageMaker Model: %s", model_name)
    return response["ModelArn"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Approve the registered model package and create a deployable SageMaker Model."
    )
    parser.add_argument(
        "--model-package-arn",
        default="",
        help="Model Package ARN to approve. Defaults to run_state.json, then latest package in the lab group.",
    )
    parser.add_argument(
        "--model-name",
        default="",
        help="Name for the deployable SageMaker Model. Defaults to <RESOURCE_PREFIX>-deployable-v<version>.",
    )
    parser.add_argument(
        "--skip-create-model",
        action="store_true",
        help="Only approve the Model Package; do not create the SageMaker Model resource.",
    )
    args = parser.parse_args()

    configure_logging()
    config = get_config()
    config.require_aws_fields()
    sm = client(config, "sagemaker")
    state = load_state()

    model_package_arn = (
        args.model_package_arn
        or state.get("model_package_arn")
        or latest_model_package_arn(sm, config.model_package_group_name)
    )
    model_package = approve_model_package(sm, model_package_arn)
    deployable_model_name = args.model_name or default_deployable_model_name(config.resource_prefix, model_package_arn)
    deployable_model_arn = None
    if not args.skip_create_model:
        deployable_model_arn = create_deployable_model(
            sm,
            model_name=deployable_model_name,
            model_package_arn=model_package_arn,
            execution_role_arn=config.sagemaker_execution_role_arn,
        )

    local_path = config.local_outputs_dir / "approved_model.json"
    output = {
        "model_package_arn": model_package_arn,
        "model_package_group_name": config.model_package_group_name,
        "model_approval_status": model_package.get("ModelApprovalStatus"),
        "deployable_model_name": deployable_model_name if not args.skip_create_model else None,
        "deployable_model_arn": deployable_model_arn,
    }
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")

    update_state(
        model_package_arn=model_package_arn,
        model_approval_status=model_package.get("ModelApprovalStatus"),
        deployable_model_name=deployable_model_name if not args.skip_create_model else None,
        deployable_model_arn=deployable_model_arn,
        approved_model_local_path=str(local_path),
    )
    LOGGER.info("Approved model package: %s", model_package_arn)
    if deployable_model_arn:
        LOGGER.info("Deployable model ARN: %s", deployable_model_arn)
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
