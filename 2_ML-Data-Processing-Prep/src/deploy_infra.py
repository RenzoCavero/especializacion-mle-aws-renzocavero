"""Deploy CloudFormation infrastructure for the lab."""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aws_clients import client, get_stack_outputs
from src.config import TEMPLATE_PATH, get_settings


FAILED_STATUSES = {
    "CREATE_FAILED",
    "ROLLBACK_FAILED",
    "ROLLBACK_COMPLETE",
    "DELETE_FAILED",
    "UPDATE_ROLLBACK_FAILED",
    "UPDATE_ROLLBACK_COMPLETE",
}


def _parameters(settings) -> List[Dict[str, str]]:
    return [
        {"ParameterKey": "ProjectName", "ParameterValue": settings.project_name},
        {"ParameterKey": "Environment", "ParameterValue": settings.environment},
        {"ParameterKey": "ResourcePrefix", "ParameterValue": settings.resource_prefix},
        {"ParameterKey": "BucketName", "ParameterValue": settings.s3_bucket_name},
        {"ParameterKey": "GlueDatabaseName", "ParameterValue": settings.glue_database_name},
        {"ParameterKey": "ExistingGlueRoleArn", "ParameterValue": settings.glue_role_arn},
        {"ParameterKey": "LogRetentionDays", "ParameterValue": "14"},
    ]


def _stack_status(cf, stack_name: str) -> Optional[str]:
    try:
        response = cf.describe_stacks(StackName=stack_name)
    except Exception:
        return None
    return response["Stacks"][0]["StackStatus"]


def _print_recent_stack_events(cf, stack_name: str, limit: int = 15) -> None:
    try:
        events = cf.describe_stack_events(StackName=stack_name)["StackEvents"]
    except Exception as exc:
        print(f"Could not read CloudFormation events: {exc}")
        return

    print(f"Recent CloudFormation events for {stack_name}:")
    for event in events[:limit]:
        reason = event.get("ResourceStatusReason", "")
        print(
            "  "
            f"{event['Timestamp']} "
            f"{event.get('LogicalResourceId')} "
            f"{event.get('ResourceType')} "
            f"{event.get('ResourceStatus')} "
            f"{reason}"
        )


def deploy() -> None:
    settings = get_settings()
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"CloudFormation template not found: {TEMPLATE_PATH}")

    cf = client("cloudformation", settings)
    template_body = TEMPLATE_PATH.read_text(encoding="utf-8")
    kwargs = {
        "StackName": settings.stack_name,
        "TemplateBody": template_body,
        "Parameters": _parameters(settings),
        "Capabilities": ["CAPABILITY_NAMED_IAM"],
        "Tags": [
            {"Key": "Project", "Value": "MLDataProcessingPrep"},
            {"Key": "Environment", "Value": "Lab"},
            {"Key": "Owner", "Value": "Student"},
            {"Key": "ManagedBy", "Value": "IaC"},
            {"Key": "CostCenter", "Value": "Training"},
            {"Key": "AutoDelete", "Value": "true"},
        ],
    }

    status = _stack_status(cf, settings.stack_name)
    exists = status is not None

    if status in FAILED_STATUSES:
        _print_recent_stack_events(cf, settings.stack_name)
        raise RuntimeError(
            f"Stack {settings.stack_name} is in {status}. "
            "Run `python -m src.destroy_infra` after reviewing the events, "
            "then retry `python -m src.deploy_infra`."
        )

    if exists:
        try:
            print(f"Updating stack {settings.stack_name} in {settings.aws_region} (current status: {status})...")
            cf.update_stack(**kwargs)
            waiter = cf.get_waiter("stack_update_complete")
            try:
                waiter.wait(StackName=settings.stack_name)
            except Exception:
                _print_recent_stack_events(cf, settings.stack_name)
                raise
        except Exception as exc:
            if "No updates are to be performed" in str(exc):
                print("Stack is already up to date.")
            else:
                raise
    else:
        print(f"Creating stack {settings.stack_name} in {settings.aws_region}...")
        cf.create_stack(OnFailure="DO_NOTHING", **kwargs)
        waiter = cf.get_waiter("stack_create_complete")
        try:
            waiter.wait(StackName=settings.stack_name)
        except Exception:
            _print_recent_stack_events(cf, settings.stack_name)
            raise

    outputs = get_stack_outputs(settings.stack_name, settings)
    print("Stack outputs:")
    for key, value in sorted(outputs.items()):
        print(f"  {key}={value}")


def main() -> None:
    deploy()


if __name__ == "__main__":
    main()
