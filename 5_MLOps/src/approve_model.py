"""Approve a candidate model in SageMaker Model Registry."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata


def _candidate_arn(config, clients, explicit_arn: str = "") -> str:
    if explicit_arn:
        return explicit_arn
    metadata_arn = read_metadata(config, "model_registry").get("model_package_arn")
    if metadata_arn:
        return str(metadata_arn)
    response = clients.sagemaker.list_model_packages(
        ModelPackageGroupName=config.model_package_group_name,
        SortBy="CreationTime",
        SortOrder="Descending",
        MaxResults=1,
    )
    packages = response.get("ModelPackageSummaryList", [])
    if not packages:
        raise ValueError(f"No model packages found in {config.model_package_group_name}.")
    return packages[0]["ModelPackageArn"]


def _has_basic_metrics(description: dict) -> bool:
    metrics = description.get("ModelMetrics", {})
    if metrics:
        return True
    customer_metadata = description.get("CustomerMetadataProperties", {})
    return any(key in customer_metadata for key in ["f1", "auc", "accuracy", "metric_f1", "metric_auc", "metric_accuracy"])


def approve(model_package_arn: str = "", reason: str = "Approved for lab deployment.", override: bool = False) -> dict:
    config = load_config(validate=True)
    clients = create_clients(config)
    arn = _candidate_arn(config, clients, model_package_arn)
    description = clients.sagemaker.describe_model_package(ModelPackageName=arn)
    if not override and not _has_basic_metrics(description):
        raise ValueError("Refusing to approve without basic metrics. Use --override only for instructor-led demos.")

    clients.sagemaker.update_model_package(
        ModelPackageArn=arn,
        ModelApprovalStatus="Approved",
        ApprovalDescription=reason[:1024],
    )
    payload = {"model_package_arn": arn, "approval_status": "Approved", "reason": reason, "override": override}
    write_metadata(config, "model_approval", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-package-arn", default="")
    parser.add_argument("--reason", default="Approved for lab deployment.")
    parser.add_argument("--override", action="store_true")
    args = parser.parse_args()
    print(json.dumps(approve(args.model_package_arn, args.reason, args.override), indent=2))


if __name__ == "__main__":
    main()
