"""Deploy base CloudFormation infrastructure and persist stack outputs.

This module intentionally accepts a blank S3_BUCKET_NAME. When no bucket is
provided, the CloudFormation template creates a lab bucket and writes the
resulting value to .env.cloud for the next lab steps.
"""

from __future__ import annotations

import os
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from .aws_clients import AwsClientError, create_session
from .config import GENERATED_ENV_FILE, ROOT_DIR, ConfigError, LabConfig, load_config, safe_name


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

OUTPUT_TO_ENV = {
    "BucketName": "S3_BUCKET_NAME",
    "SageMakerExecutionRoleArn": "SAGEMAKER_EXECUTION_ROLE_ARN",
    "LambdaExecutionRoleArn": "LAMBDA_EXECUTION_ROLE_ARN",
    "StepFunctionsRoleArn": "STEPFUNCTIONS_ROLE_ARN",
    "EventBridgeToStepFunctionsRoleArn": "EVENTBRIDGE_TO_SFN_ROLE_ARN",
    "ModelPackageGroupName": "MODEL_PACKAGE_GROUP_NAME",
}


def resolve_stack_name(config: LabConfig) -> str:
    return safe_name(os.getenv("STACK_NAME", f"{config.resource_prefix}-stack"))


def resolve_create_bucket(config: LabConfig) -> str:
    raw = os.getenv("CREATE_BUCKET", "").strip().lower()
    if raw in {"true", "false"}:
        return raw
    return "false" if config.s3_bucket_name else "true"


def stack_parameters(config: LabConfig) -> list[dict[str, str]]:
    return [
        {"ParameterKey": "ProjectName", "ParameterValue": config.project_name},
        {"ParameterKey": "Environment", "ParameterValue": config.environment},
        {"ParameterKey": "ResourcePrefix", "ParameterValue": config.resource_prefix},
        {"ParameterKey": "CreateBucket", "ParameterValue": resolve_create_bucket(config)},
        {"ParameterKey": "ExistingBucketName", "ParameterValue": config.s3_bucket_name},
        {"ParameterKey": "ModelPackageGroupName", "ParameterValue": config.model_package_group_name},
        {"ParameterKey": "KmsKeyArn", "ParameterValue": config.kms_key_arn},
    ]


def stack_tags(config: LabConfig) -> list[dict[str, str]]:
    return [
        {"Key": tag["Key"], "Value": tag["Value"]}
        for tag in config.tags
        if tag["Key"] in {"Project", "Environment", "Owner", "ManagedBy", "CostCenter", "AutoDelete"}
    ]


def _arn_account_id(value: str) -> str:
    parts = value.split(":")
    if len(parts) >= 5 and parts[0] == "arn":
        return parts[4]
    return ""


def _generated_env_has_cross_account_values(config: LabConfig, account_id: str) -> bool:
    generated_arns = [
        config.sagemaker_execution_role_arn,
        config.lambda_execution_role_arn,
        config.stepfunctions_role_arn,
        config.eventbridge_to_sfn_role_arn,
    ]
    return any(_arn_account_id(value) and _arn_account_id(value) != account_id for value in generated_arns)


def _ignore_stale_generated_outputs(config: LabConfig, account_id: str) -> LabConfig:
    if not _generated_env_has_cross_account_values(config, account_id):
        return config
    print(
        "Detected .env.cloud values from a different AWS account. "
        f"Current account is {account_id}; generated outputs will be ignored and refreshed."
    )
    return replace(
        config,
        s3_bucket_name="",
        sagemaker_execution_role_arn="",
        lambda_execution_role_arn="",
        stepfunctions_role_arn="",
        eventbridge_to_sfn_role_arn="",
    )


def get_stack_status(cf: Any, stack_name: str) -> str | None:
    try:
        response = cf.describe_stacks(StackName=stack_name)
        return response["Stacks"][0]["StackStatus"]
    except Exception as exc:
        response = getattr(exc, "response", {}) or {}
        message = response.get("Error", {}).get("Message", "")
        code = response.get("Error", {}).get("Code", "")
        if code == "ValidationError" and "does not exist" in message:
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


def describe_outputs(cf: Any, stack_name: str) -> dict[str, str]:
    response = cf.describe_stacks(StackName=stack_name)
    outputs = response["Stacks"][0].get("Outputs", [])
    return {item["OutputKey"]: item.get("OutputValue", "") for item in outputs}


def write_env_cloud(path: Path, stack_name: str, outputs: dict[str, str]) -> Path:
    lines = [
        "# Generated by python -m src.deploy_infra.",
        "# Do not commit real account-specific values.",
        f"STACK_NAME={stack_name}",
    ]
    for output_name, env_name in OUTPUT_TO_ENV.items():
        value = outputs.get(output_name, "")
        if value:
            lines.append(f"{env_name}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def deploy_infra() -> dict[str, str]:
    config = load_config(validate=False)
    if not config.aws_region:
        raise ConfigError("AWS_REGION is required. Set it in .env or export it before deploying infrastructure.")

    session = create_session(config)
    account_id = session.client("sts").get_caller_identity()["Account"]
    config = _ignore_stale_generated_outputs(config, account_id)
    cf = session.client("cloudformation")
    stack_name = resolve_stack_name(config)
    template_body = (ROOT_DIR / "infra" / "cloudformation" / "template.yaml").read_text(encoding="utf-8")

    status = get_stack_status(cf, stack_name)
    if status in IN_PROGRESS_STATUSES:
        status = wait_until_stable(cf, stack_name, status)
    status = delete_failed_stack_if_needed(cf, stack_name, status)

    if status is None:
        print(f"Creating CloudFormation stack {stack_name}...")
        cf.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=stack_parameters(config),
            Capabilities=["CAPABILITY_NAMED_IAM"],
            Tags=stack_tags(config),
        )
        cf.get_waiter("stack_create_complete").wait(StackName=stack_name)
    else:
        print(f"Updating CloudFormation stack {stack_name} from {status}...")
        try:
            cf.update_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=stack_parameters(config),
                Capabilities=["CAPABILITY_NAMED_IAM"],
                Tags=stack_tags(config),
            )
            cf.get_waiter("stack_update_complete").wait(StackName=stack_name)
        except Exception as exc:
            message = getattr(exc, "response", {}).get("Error", {}).get("Message", "")
            if "No updates are to be performed" not in message:
                raise
            print("No CloudFormation updates were needed.")

    outputs = describe_outputs(cf, stack_name)
    write_env_cloud(GENERATED_ENV_FILE, stack_name, outputs)
    print(f"Infrastructure ready. Outputs were written to {GENERATED_ENV_FILE.relative_to(ROOT_DIR)}.")
    return outputs


def main() -> None:
    outputs = deploy_infra()
    for output_name, value in outputs.items():
        print(f"{output_name}: {value}")


if __name__ == "__main__":
    try:
        main()
    except (AwsClientError, ConfigError) as exc:
        raise SystemExit(str(exc))
