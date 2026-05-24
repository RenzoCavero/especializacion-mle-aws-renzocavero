from __future__ import annotations

import logging
from botocore.exceptions import ClientError, WaiterError

from src.aws_clients import client
from src.cleanup_resources import delete_s3_objects
from src.cleanup_resources import main as cleanup_sagemaker_resources
from src.config import get_config
from src.logging_utils import configure_logging


LOGGER = logging.getLogger(__name__)


def stack_exists(cf, stack_name: str) -> bool:
    try:
        cf.describe_stacks(StackName=stack_name)
        return True
    except ClientError as exc:
        message = exc.response.get("Error", {}).get("Message", "")
        if "does not exist" in message:
            return False
        raise


def stack_owned_bucket_name(cf, stack_name: str) -> str | None:
    try:
        response = cf.describe_stack_resource(StackName=stack_name, LogicalResourceId="LabBucket")
        return response["StackResourceDetail"].get("PhysicalResourceId")
    except ClientError as exc:
        message = exc.response.get("Error", {}).get("Message", "")
        code = exc.response.get("Error", {}).get("Code")
        if "does not exist" in message or code in {"ValidationError", "ResourceNotFoundException"}:
            return None
        raise


def empty_stack_bucket_if_owned(config, cf) -> None:
    bucket_name = stack_owned_bucket_name(cf, config.stack_name)
    if not bucket_name:
        LOGGER.info("No stack-owned LabBucket found for %s", config.stack_name)
        return
    if bucket_name != config.s3_bucket_name:
        LOGGER.warning(
            "Stack LabBucket is %s but config points to %s. Not deleting S3 objects automatically.",
            bucket_name,
            config.s3_bucket_name,
        )
        return
    LOGGER.info("Emptying stack-owned S3 bucket %s before CloudFormation deletion", bucket_name)
    delete_s3_objects(config)


def recent_failure_events(cf, stack_name: str) -> list[str]:
    try:
        response = cf.describe_stack_events(StackName=stack_name)
    except ClientError:
        return []
    failures = []
    for event in response.get("StackEvents", []):
        status = event.get("ResourceStatus", "")
        reason = event.get("ResourceStatusReason", "")
        if "FAILED" in status:
            failures.append(
                f"{event.get('LogicalResourceId')} {status}: {reason}".strip()
            )
        if len(failures) >= 5:
            break
    return failures


def main() -> None:
    configure_logging()
    config = get_config()
    cleanup_sagemaker_resources()
    cf = client(config, "cloudformation")
    if not stack_exists(cf, config.stack_name):
        LOGGER.info("CloudFormation stack %s does not exist.", config.stack_name)
        return
    empty_stack_bucket_if_owned(config, cf)
    try:
        cf.delete_stack(StackName=config.stack_name)
        LOGGER.info("Requested deletion of CloudFormation stack %s", config.stack_name)
        cf.get_waiter("stack_delete_complete").wait(StackName=config.stack_name)
        LOGGER.info("CloudFormation stack deleted: %s", config.stack_name)
    except WaiterError as exc:
        failures = recent_failure_events(cf, config.stack_name)
        detail = "\n".join(failures) if failures else str(exc)
        raise RuntimeError(
            "CloudFormation stack deletion failed. Review the recent failure events below, "
            "fix the remaining resource, and re-run bash scripts/lab.sh cleanup.\n"
            f"{detail}"
        ) from exc
    except ClientError as exc:
        message = exc.response.get("Error", {}).get("Message", "")
        if "does not exist" in message:
            LOGGER.info("CloudFormation stack %s does not exist.", config.stack_name)
            return
        raise


if __name__ == "__main__":
    main()
