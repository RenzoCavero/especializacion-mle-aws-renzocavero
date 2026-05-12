"""Destroy lab infrastructure and optionally empty the lab bucket."""

from __future__ import annotations

import argparse
from typing import List, Optional

from src.aws_clients import client, get_stack_outputs
from src.config import get_settings


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


def _stack_resource_physical_id(cf, stack_name: str, logical_id: str) -> Optional[str]:
    try:
        resources = cf.describe_stack_resources(StackName=stack_name)["StackResources"]
    except Exception:
        return None
    for resource in resources:
        if resource.get("LogicalResourceId") == logical_id:
            return resource.get("PhysicalResourceId")
    return None


def _is_error_code(exc: Exception, code: str) -> bool:
    return getattr(exc, "response", {}).get("Error", {}).get("Code") == code


def _empty_bucket(s3, bucket_name: str) -> None:
    print(f"Emptying s3://{bucket_name}/ before stack deletion...")
    paginator = s3.get_paginator("list_object_versions")
    to_delete: List[dict] = []
    try:
        for page in paginator.paginate(Bucket=bucket_name):
            for item in page.get("Versions", []) + page.get("DeleteMarkers", []):
                to_delete.append({"Key": item["Key"], "VersionId": item["VersionId"]})
                if len(to_delete) == 1000:
                    s3.delete_objects(Bucket=bucket_name, Delete={"Objects": to_delete})
                    to_delete = []
        if to_delete:
            s3.delete_objects(Bucket=bucket_name, Delete={"Objects": to_delete})
    except Exception as exc:
        if _is_error_code(exc, "NoSuchBucket"):
            print(f"Bucket s3://{bucket_name}/ does not exist. Continuing with stack deletion.")
            return
        raise

    paginator = s3.get_paginator("list_objects_v2")
    batch: List[dict] = []
    try:
        for page in paginator.paginate(Bucket=bucket_name):
            for item in page.get("Contents", []):
                batch.append({"Key": item["Key"]})
                if len(batch) == 1000:
                    s3.delete_objects(Bucket=bucket_name, Delete={"Objects": batch})
                    batch = []
        if batch:
            s3.delete_objects(Bucket=bucket_name, Delete={"Objects": batch})
    except Exception as exc:
        if _is_error_code(exc, "NoSuchBucket"):
            print(f"Bucket s3://{bucket_name}/ does not exist. Continuing with stack deletion.")
            return
        raise


def _delete_data_quality_ruleset(glue, ruleset_name: str) -> None:
    if not ruleset_name:
        return
    try:
        glue.delete_data_quality_ruleset(Name=ruleset_name)
        print(f"Deleted Glue Data Quality ruleset {ruleset_name}.")
    except glue.exceptions.EntityNotFoundException:
        return
    except Exception as exc:
        print(f"Could not delete Glue Data Quality ruleset {ruleset_name}: {exc}")


def destroy(retain_glue_role: bool = False) -> None:
    settings = get_settings()
    cf = client("cloudformation", settings)
    s3 = client("s3", settings)
    glue = client("glue", settings)
    try:
        outputs = get_stack_outputs(settings.stack_name, settings)
    except Exception:
        outputs = {}

    bucket = outputs.get("BucketName") or settings.s3_bucket_name
    if not bucket:
        bucket = _stack_resource_physical_id(cf, settings.stack_name, "LabBucket")

    if bucket and settings.empty_bucket_on_destroy:
        _empty_bucket(s3, bucket)

    _delete_data_quality_ruleset(glue, settings.glue_data_quality_ruleset_name)

    print(f"Deleting stack {settings.stack_name}...")
    delete_kwargs = {"StackName": settings.stack_name}
    if retain_glue_role:
        print("Retaining GlueProcessingRole so the stack can delete without IAM role delete permissions.")
        delete_kwargs["RetainResources"] = ["GlueProcessingRole"]
    cf.delete_stack(**delete_kwargs)
    waiter = cf.get_waiter("stack_delete_complete")
    try:
        waiter.wait(StackName=settings.stack_name)
    except Exception:
        _print_recent_stack_events(cf, settings.stack_name)
        raise
    print("Stack deleted.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Destroy lab CloudFormation stack.")
    parser.add_argument(
        "--retain-glue-role",
        action="store_true",
        help="Retain the GlueProcessingRole resource. Useful when stack deletion fails because the caller lacks iam:DeleteRolePolicy.",
    )
    args = parser.parse_args()
    destroy(retain_glue_role=args.retain_glue_role)


if __name__ == "__main__":
    main()
