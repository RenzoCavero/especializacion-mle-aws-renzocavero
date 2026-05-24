"""Create or update the SageMaker model build pipeline."""

from __future__ import annotations

import argparse
import json

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - only used when boto3/botocore is absent locally
    class ClientError(Exception):
        response = {"Error": {"Code": "Unknown"}}

from pipelines.build.pipeline_definition import save_pipeline_contract, upsert_pipeline

from .aws_clients import create_clients
from .config import load_config, write_metadata


def ensure_model_package_group() -> dict[str, str]:
    config = load_config(validate=True)
    clients = create_clients(config)
    try:
        clients.sagemaker.describe_model_package_group(ModelPackageGroupName=config.model_package_group_name)
        status = "existing"
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code not in {"ValidationException", "ResourceNotFound"}:
            raise
        clients.sagemaker.create_model_package_group(
            ModelPackageGroupName=config.model_package_group_name,
            ModelPackageGroupDescription="Model package group for the AWS MLOps educational lab.",
            Tags=config.tags,
        )
        status = "created"
    return {"model_package_group_name": config.model_package_group_name, "status": status}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update SageMaker build pipeline.")
    parser.add_argument("--contract-only", action="store_true", help="Only write local pipeline contract.")
    args = parser.parse_args()

    config = load_config(validate=not args.contract_only, require_execution_role=not args.contract_only)
    contract_path = save_pipeline_contract(config)
    payload = {"contract_path": str(contract_path), "pipeline_name": config.pipeline_name}

    if args.contract_only:
        payload["mode"] = "contract-only"
    else:
        group = ensure_model_package_group()
        response = upsert_pipeline(config)
        payload.update({"mode": "cloud", "model_package_group": group, "upsert_response": response})

    write_metadata(config, "pipeline_upsert", payload)
    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    try:
        main()
    except (ClientError, RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc))
