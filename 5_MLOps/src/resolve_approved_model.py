"""Resolve the latest approved model package."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, write_metadata


def resolve_approved_model() -> dict[str, object]:
    config = load_config(validate=True)

    if config.model_artifact_s3_uri and not config.model_package_arn:
        payload = {
            "model_package_group_name": config.model_package_group_name,
            "model_package_arn": "",
            "model_artifact_s3_uri": config.model_artifact_s3_uri,
            "image_uri": config.model_image_uri,
            "approval_status": "ExternalArtifact",
            "metadata": {
                "source": "MODEL_ARTIFACT_S3_URI",
                "note": "Integrated mode artifact. Provide MODEL_IMAGE_URI for deployment.",
            },
        }
        write_metadata(config, "approved_model", payload)
        return payload

    clients = create_clients(config)

    if config.model_package_arn:
        description = clients.sagemaker.describe_model_package(ModelPackageName=config.model_package_arn)
        if description.get("ModelApprovalStatus") != "Approved":
            raise ValueError(f"Configured MODEL_PACKAGE_ARN is not Approved: {config.model_package_arn}")
        arn = config.model_package_arn
    else:
        paginator = clients.sagemaker.get_paginator("list_model_packages")
        arn = ""
        description = {}
        for page in paginator.paginate(
            ModelPackageGroupName=config.model_package_group_name,
            ModelApprovalStatus="Approved",
            SortBy="CreationTime",
            SortOrder="Descending",
        ):
            packages = page.get("ModelPackageSummaryList", [])
            if packages:
                arn = packages[0]["ModelPackageArn"]
                description = clients.sagemaker.describe_model_package(ModelPackageName=arn)
                break
        if not arn:
            raise ValueError(f"No Approved model package found in {config.model_package_group_name}.")

    containers = description.get("InferenceSpecification", {}).get("Containers", [])
    artifact_uri = containers[0].get("ModelDataUrl", "") if containers else ""
    image_uri = containers[0].get("Image", "") if containers else ""
    payload = {
        "model_package_group_name": config.model_package_group_name,
        "model_package_arn": arn,
        "model_artifact_s3_uri": artifact_uri,
        "image_uri": image_uri,
        "approval_status": description.get("ModelApprovalStatus"),
        "metadata": description.get("CustomerMetadataProperties", {}),
    }
    write_metadata(config, "approved_model", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(resolve_approved_model(), indent=2, default=str))


if __name__ == "__main__":
    main()
