from __future__ import annotations

import logging
import time
from botocore.exceptions import ClientError

from src.aws_clients import client
from src.config import ENV_FILE, PROJECT_ROOT, get_config
from src.fetch_stack_outputs import write_stack_outputs
from src.logging_utils import configure_logging


LOGGER = logging.getLogger(__name__)


FAILED_CREATE_STATUSES = {
    "CREATE_FAILED",
    "ROLLBACK_COMPLETE",
    "ROLLBACK_FAILED",
}

IN_PROGRESS_STATUSES = {
    "CREATE_IN_PROGRESS",
    "ROLLBACK_IN_PROGRESS",
    "DELETE_IN_PROGRESS",
    "UPDATE_IN_PROGRESS",
    "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
    "UPDATE_ROLLBACK_IN_PROGRESS",
    "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
}


def get_stack_status(cf, stack_name: str) -> str | None:
    try:
        response = cf.describe_stacks(StackName=stack_name)
        return response["Stacks"][0]["StackStatus"]
    except ClientError as exc:
        message = exc.response.get("Error", {}).get("Message", "")
        if "does not exist" in message:
            return None
        raise


def wait_until_stack_stable(cf, stack_name: str, status: str, timeout_seconds: int = 900) -> str | None:
    deadline = time.time() + timeout_seconds
    current_status = status
    while current_status in IN_PROGRESS_STATUSES:
        if current_status == "DELETE_IN_PROGRESS":
            LOGGER.info("Waiting for previous delete operation to finish for stack %s", stack_name)
        else:
            LOGGER.info("Waiting for stack %s to leave status %s", stack_name, current_status)
        time.sleep(15)
        if time.time() > deadline:
            raise TimeoutError(f"Timed out waiting for stack {stack_name} to leave {current_status}")
        current_status = get_stack_status(cf, stack_name)
        if current_status is None:
            return None
    return current_status


def wait_for_existing_operation(cf, stack_name: str, status: str) -> str | None:
    if status == "DELETE_IN_PROGRESS":
        return wait_until_stack_stable(cf, stack_name, status)
    if status == "CREATE_IN_PROGRESS":
        LOGGER.info("Waiting for previous create operation to finish for stack %s", stack_name)
        try:
            cf.get_waiter("stack_create_complete").wait(StackName=stack_name)
        except ClientError:
            return get_stack_status(cf, stack_name)
    if status.startswith("UPDATE_"):
        LOGGER.info("Waiting for previous update operation to finish for stack %s", stack_name)
        try:
            cf.get_waiter("stack_update_complete").wait(StackName=stack_name)
        except ClientError:
            return get_stack_status(cf, stack_name)
    return wait_until_stack_stable(cf, stack_name, get_stack_status(cf, stack_name) or status)


def delete_failed_stack_if_needed(cf, stack_name: str, status: str | None) -> str | None:
    if status not in FAILED_CREATE_STATUSES:
        return status
    LOGGER.warning(
        "Stack %s is in %s. Deleting it before retrying deployment.",
        stack_name,
        status,
    )
    cf.delete_stack(StackName=stack_name)
    cf.get_waiter("stack_delete_complete").wait(StackName=stack_name)
    return None


def env_file_value(key: str) -> str:
    if not ENV_FILE.exists():
        return ""
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        item_key, value = line.split("=", 1)
        if item_key.strip() == key:
            return value.strip().strip('"').strip("'")
    return ""


def stack_parameters(config) -> list[dict[str, str]]:
    return [
        {"ParameterKey": "ProjectName", "ParameterValue": config.project_name},
        {"ParameterKey": "Environment", "ParameterValue": config.environment},
        {"ParameterKey": "ResourcePrefix", "ParameterValue": config.resource_prefix},
        {"ParameterKey": "S3BucketName", "ParameterValue": env_file_value("S3_BUCKET_NAME")},
        {"ParameterKey": "LogRetentionDays", "ParameterValue": "14"},
    ]


def stack_tags() -> list[dict[str, str]]:
    return [
        {"Key": "Project", "Value": "MLModelTrainingOptimization"},
        {"Key": "Environment", "Value": "Lab"},
        {"Key": "Owner", "Value": "Student"},
        {"Key": "ManagedBy", "Value": "IaC"},
        {"Key": "CostCenter", "Value": "Training"},
        {"Key": "AutoDelete", "Value": "true"},
    ]


def main() -> None:
    configure_logging()
    config = get_config()
    cf = client(config, "cloudformation")
    template_body = (PROJECT_ROOT / "infra" / "cloudformation" / "template.yaml").read_text(encoding="utf-8")
    status = get_stack_status(cf, config.stack_name)
    if status in IN_PROGRESS_STATUSES:
        status = wait_for_existing_operation(cf, config.stack_name, status)
    status = delete_failed_stack_if_needed(cf, config.stack_name, status)
    exists = status is not None

    if exists:
        LOGGER.info("Updating CloudFormation stack %s from status %s", config.stack_name, status)
        try:
            cf.update_stack(
                StackName=config.stack_name,
                TemplateBody=template_body,
                Parameters=stack_parameters(config),
                Capabilities=["CAPABILITY_IAM"],
                Tags=stack_tags(),
            )
            cf.get_waiter("stack_update_complete").wait(StackName=config.stack_name)
        except ClientError as exc:
            message = exc.response.get("Error", {}).get("Message", "")
            if "No updates are to be performed" not in message:
                raise
            LOGGER.info("No CloudFormation updates were needed.")
    else:
        LOGGER.info("Creating CloudFormation stack %s", config.stack_name)
        cf.create_stack(
            StackName=config.stack_name,
            TemplateBody=template_body,
            Parameters=stack_parameters(config),
            Capabilities=["CAPABILITY_IAM"],
            Tags=stack_tags(),
        )
        cf.get_waiter("stack_create_complete").wait(StackName=config.stack_name)

    outputs = write_stack_outputs(config)
    LOGGER.info("Infrastructure ready. Bucket: %s", outputs.get("BucketName"))


if __name__ == "__main__":
    main()
