from __future__ import annotations

import argparse
import os
import time
from typing import Any

from .aws_clients import client_error_code, clients
from .config import ROOT_DIR, ConfigError, load_config
from .fetch_stack_outputs import write_stack_outputs

FAILED_CREATE_STATUSES = {"CREATE_FAILED", "ROLLBACK_COMPLETE", "ROLLBACK_FAILED"}
IN_PROGRESS_STATUSES = {
    "CREATE_IN_PROGRESS",
    "ROLLBACK_IN_PROGRESS",
    "DELETE_IN_PROGRESS",
    "UPDATE_IN_PROGRESS",
    "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
    "UPDATE_ROLLBACK_IN_PROGRESS",
    "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
}


def get_stack_status(cf: Any, stack_name: str) -> str | None:
    try:
        response = cf.describe_stacks(StackName=stack_name)
        return response["Stacks"][0]["StackStatus"]
    except Exception as exc:
        message = getattr(exc, "response", {}).get("Error", {}).get("Message", "")
        if "does not exist" in message:
            return None
        if client_error_code(exc) == "ValidationError" and "does not exist" in message:
            return None
        raise


def wait_until_stable(cf: Any, stack_name: str, status: str, timeout_seconds: int = 1200) -> str | None:
    deadline = time.time() + timeout_seconds
    current = status
    while current in IN_PROGRESS_STATUSES:
        print(f"Waiting for stack {stack_name} to leave {current}...")
        time.sleep(15)
        if time.time() > deadline:
            raise TimeoutError(f"Timed out waiting for stack {stack_name}.")
        current = get_stack_status(cf, stack_name)
        if current is None:
            return None
    return current


def delete_failed_stack_if_needed(cf: Any, stack_name: str, status: str | None) -> str | None:
    if status not in FAILED_CREATE_STATUSES:
        return status
    print(f"Stack {stack_name} is in {status}. Deleting before retrying.")
    cf.delete_stack(StackName=stack_name)
    cf.get_waiter("stack_delete_complete").wait(StackName=stack_name)
    return None


def stack_parameters(config) -> list[dict[str, str]]:
    requested_create_bucket = os.getenv("CREATE_BUCKET", "").strip().lower()
    if requested_create_bucket in {"true", "false"}:
        create_bucket = requested_create_bucket
    else:
        create_bucket = "false" if config.s3_bucket_name else "true"
    return [
        {"ParameterKey": "ProjectName", "ParameterValue": config.project_name},
        {"ParameterKey": "Environment", "ParameterValue": config.environment},
        {"ParameterKey": "ResourcePrefix", "ParameterValue": config.resource_prefix},
        {"ParameterKey": "CreateBucket", "ParameterValue": create_bucket},
        {"ParameterKey": "ExistingBucketName", "ParameterValue": config.s3_bucket_name},
        {"ParameterKey": "KmsKeyArn", "ParameterValue": config.kms_key_id},
    ]


def stack_tags() -> list[dict[str, str]]:
    return [
        {"Key": "Project", "Value": "MLModelDeployment"},
        {"Key": "Environment", "Value": "Lab"},
        {"Key": "Owner", "Value": "LabUser"},
        {"Key": "ManagedBy", "Value": "IaC"},
        {"Key": "CostCenter", "Value": "Training"},
        {"Key": "AutoDelete", "Value": "true"},
    ]


def deploy_infra() -> dict[str, str]:
    config = load_config(require_aws=False)
    if not config.aws_region:
        raise ConfigError("AWS_REGION es requerido para desplegar infraestructura.")
    cf = clients(config).cloudformation
    template_body = (ROOT_DIR / "infra" / "cloudformation" / "template.yaml").read_text(
        encoding="utf-8"
    )
    status = get_stack_status(cf, config.stack_name)
    if status in IN_PROGRESS_STATUSES:
        status = wait_until_stable(cf, config.stack_name, status)
    status = delete_failed_stack_if_needed(cf, config.stack_name, status)

    if status is None:
        print(f"Creating CloudFormation stack {config.stack_name}...")
        cf.create_stack(
            StackName=config.stack_name,
            TemplateBody=template_body,
            Parameters=stack_parameters(config),
            Capabilities=["CAPABILITY_NAMED_IAM"],
            Tags=stack_tags(),
        )
        cf.get_waiter("stack_create_complete").wait(StackName=config.stack_name)
    else:
        print(f"Updating CloudFormation stack {config.stack_name} from {status}...")
        try:
            cf.update_stack(
                StackName=config.stack_name,
                TemplateBody=template_body,
                Parameters=stack_parameters(config),
                Capabilities=["CAPABILITY_NAMED_IAM"],
                Tags=stack_tags(),
            )
            cf.get_waiter("stack_update_complete").wait(StackName=config.stack_name)
        except Exception as exc:
            message = getattr(exc, "response", {}).get("Error", {}).get("Message", "")
            if "No updates are to be performed" not in message:
                raise
            print("No CloudFormation updates were needed.")

    outputs = write_stack_outputs()
    print("Infrastructure ready. .env.cloud was generated automatically.")
    return outputs


def main() -> None:
    argparse.ArgumentParser(description="Deploy Lab 04 CloudFormation infrastructure.").parse_args()
    try:
        deploy_infra()
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
