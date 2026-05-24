"""Collect Model Registry metadata for local reporting."""

from __future__ import annotations

import argparse
import json
from typing import Any

from .aws_clients import create_clients
from .config import LabConfig, load_config, write_metadata
from .config import read_metadata


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    bucket_key = uri[5:]
    bucket, _, key = bucket_key.partition("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI without bucket/key: {uri}")
    return bucket, key


def _evaluation_s3_uri(description: dict[str, Any]) -> str:
    return (
        description.get("ModelMetrics", {})
        .get("ModelQuality", {})
        .get("Statistics", {})
        .get("S3Uri", "")
    )


def extract_evaluation_metrics(payload: dict[str, Any]) -> dict[str, float]:
    """Extract common model quality metrics from the SageMaker evaluation JSON."""

    raw_metrics = payload.get("metrics", {})
    nested_metrics = payload.get("binary_classification_metrics", {})
    metrics: dict[str, float] = {}
    for name in ("accuracy", "f1", "auc"):
        raw_value = raw_metrics.get(name)
        if raw_value is None:
            raw_value = nested_metrics.get(name, {}).get("value")
        if raw_value is not None:
            metrics[name] = float(raw_value)
    return metrics


def metadata_from_metrics(config: LabConfig, metrics: dict[str, float], evaluation_s3_uri: str) -> dict[str, str]:
    """Format metrics as SageMaker Model Package customer metadata."""

    metadata = {
        f"metric_{name}": f"{value:.6f}"
        for name, value in metrics.items()
    }
    metadata.update(
        {
            "quality_gate_f1_threshold": f"{config.f1_threshold:.6f}",
            "quality_gate_auc_threshold": f"{config.auc_threshold:.6f}",
            "evaluation_s3_uri": evaluation_s3_uri,
        }
    )
    return metadata


def _load_evaluation_payload(s3_client: Any, evaluation_s3_uri: str) -> dict[str, Any]:
    bucket, key = _parse_s3_uri(evaluation_s3_uri)
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))


def _mirror_metrics_to_customer_metadata(
    *,
    config: LabConfig,
    clients: Any,
    model_package_arn: str,
    description: dict[str, Any],
) -> dict[str, Any]:
    evaluation_s3_uri = _evaluation_s3_uri(description)
    if not evaluation_s3_uri:
        return {
            "status": "skipped",
            "reason": "Model package does not include ModelMetrics.ModelQuality.Statistics.S3Uri.",
        }

    payload = _load_evaluation_payload(clients.s3, evaluation_s3_uri)
    metrics = extract_evaluation_metrics(payload)
    if not metrics:
        return {
            "status": "skipped",
            "evaluation_s3_uri": evaluation_s3_uri,
            "reason": "No accuracy, f1 or auc metrics were found in the evaluation artifact.",
        }

    customer_metadata = metadata_from_metrics(config, metrics, evaluation_s3_uri)
    existing_metadata = description.get("CustomerMetadataProperties", {})
    update_required = any(existing_metadata.get(key) != value for key, value in customer_metadata.items())
    if update_required:
        clients.sagemaker.update_model_package(
            ModelPackageArn=model_package_arn,
            CustomerMetadataProperties=customer_metadata,
        )

    return {
        "status": "updated" if update_required else "already_current",
        "evaluation_s3_uri": evaluation_s3_uri,
        "metrics": metrics,
        "customer_metadata": customer_metadata,
    }


def latest_model_package() -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    response = clients.sagemaker.list_model_packages(
        ModelPackageGroupName=config.model_package_group_name,
        SortBy="CreationTime",
        SortOrder="Descending",
        MaxResults=1,
    )
    packages = response.get("ModelPackageSummaryList", [])
    if not packages:
        execution_status = read_metadata(config, "pipeline_execution_status")
        steps = execution_status.get("steps", [])
        quality_gate = next((step for step in steps if step.get("StepName") == "QualityGate"), {})
        outcome = quality_gate.get("Metadata", {}).get("Condition", {}).get("Outcome")
        if outcome == "False":
            raise ValueError(
                f"No model packages found in {config.model_package_group_name} because the pipeline QualityGate "
                "evaluated to False. Review artifacts/local_outputs/pipeline_execution_status.json and the "
                "evaluation metrics, then rerun step 02 and step 05 before step 06."
            )
        raise ValueError(
            f"No model packages found in {config.model_package_group_name}. "
            "Confirm that step 05 completed and that QualityGate registered the model."
        )
    arn = packages[0]["ModelPackageArn"]
    description = clients.sagemaker.describe_model_package(ModelPackageName=arn)
    metrics_update = _mirror_metrics_to_customer_metadata(
        config=config,
        clients=clients,
        model_package_arn=arn,
        description=description,
    )
    if metrics_update.get("status") == "updated":
        description = clients.sagemaker.describe_model_package(ModelPackageName=arn)
    payload = {
        "model_package_group_name": config.model_package_group_name,
        "model_package_arn": arn,
        "approval_status": description.get("ModelApprovalStatus"),
        "evaluation_s3_uri": metrics_update.get("evaluation_s3_uri", _evaluation_s3_uri(description)),
        "metrics": metrics_update.get("metrics", {}),
        "visible_metrics_update": metrics_update,
        "description": description,
    }
    write_metadata(config, "model_registry", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(latest_model_package(), indent=2, default=str))


if __name__ == "__main__":
    main()
