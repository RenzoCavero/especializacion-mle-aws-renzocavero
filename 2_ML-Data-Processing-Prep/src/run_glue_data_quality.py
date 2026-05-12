"""Run an optional AWS Glue Data Quality ruleset evaluation."""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict

from src.aws_clients import (
    client,
    get_bucket_name,
    get_glue_data_quality_ruleset_name,
    get_glue_database_name,
    get_processing_role_arn,
)
from src.config import get_settings
from src.data_utils import utc_now_iso
from src.glue_catalog import register_all_tables, sync_catalog_data
from src.s3_io import write_json_to_s3


TARGET_TABLE = "features_training"
TARGET_KEY = "features/training_dataset.csv"

FEATURES_TRAINING_RULESET = """Rules = [
  IsComplete "transaction_id",
  IsComplete "customer_id",
  IsComplete "amount",
  IsComplete "is_fraud",
  ColumnValues "amount" > 0,
  ColumnValues "is_fraud" in [0, 1],
  ColumnValues "split" in ["train", "validation", "test"]
]"""


def _ensure_ruleset(glue_client: Any, ruleset_name: str, database_name: str) -> None:
    description = "Basic AWS Glue Data Quality rules for lab training features."
    try:
        glue_client.get_data_quality_ruleset(Name=ruleset_name)
        glue_client.update_data_quality_ruleset(
            Name=ruleset_name,
            Description=description,
            Ruleset=FEATURES_TRAINING_RULESET,
        )
        print(f"Updated Glue Data Quality ruleset {ruleset_name}")
        return
    except glue_client.exceptions.EntityNotFoundException:
        pass

    try:
        glue_client.create_data_quality_ruleset(
            Name=ruleset_name,
            Description=description,
            Ruleset=FEATURES_TRAINING_RULESET,
            TargetTable={"DatabaseName": database_name, "TableName": TARGET_TABLE},
            Tags={
                "Project": "MLDataProcessingPrep",
                "Environment": "Lab",
                "ManagedBy": "LabScript",
            },
            ClientToken=str(uuid.uuid4()),
        )
        print(f"Created Glue Data Quality ruleset {ruleset_name}")
    except glue_client.exceptions.AlreadyExistsException:
        glue_client.update_data_quality_ruleset(
            Name=ruleset_name,
            Description=description,
            Ruleset=FEATURES_TRAINING_RULESET,
        )
        print(f"Updated Glue Data Quality ruleset {ruleset_name}")
    except glue_client.exceptions.InvalidInputException as exc:
        if "same resourceName but a different internalId already exists" not in str(exc):
            raise
        glue_client.update_data_quality_ruleset(
            Name=ruleset_name,
            Description=description,
            Ruleset=FEATURES_TRAINING_RULESET,
        )
        print(f"Updated Glue Data Quality ruleset {ruleset_name}")


def _wait_for_run(glue_client: Any, run_id: str, poll_seconds: int) -> Dict[str, object]:
    while True:
        run = glue_client.get_data_quality_ruleset_evaluation_run(RunId=run_id)
        status = run.get("Status", "UNKNOWN")
        print(f"Glue Data Quality run state: {status}")
        if status in {"SUCCEEDED", "FAILED", "STOPPED", "TIMEOUT"}:
            if status != "SUCCEEDED":
                raise RuntimeError(_format_failure_message(status, run))
            return run
        time.sleep(poll_seconds)


def _format_failure_message(status: str, run: Dict[str, object]) -> str:
    error = str(run.get("ErrorString", ""))
    role = run.get("Role", "<glue-execution-role>")
    if "aws-glue-ml-data-quality-assets" in error and "Access Denied" in error:
        return (
            "Glue Data Quality run failed because the Glue execution role cannot read "
            "AWS Glue Data Quality managed assets from S3. Add `s3:GetObject` on "
            "`arn:aws:s3:::aws-glue-ml-data-quality-assets-<region>/*` to the role "
            f"`{role}`. If the role is managed by this lab stack, run "
            "`bash scripts/deploy_infra.sh` to update the IAM policy, then rerun "
            "`bash scripts/run_glue_data_quality.sh`. Original AWS error: "
            f"{error}"
        )
    if "glue:GetDataQualityRulesetEvaluationRun" in error and "AccessDenied" in error:
        return (
            "Glue Data Quality run failed because the Glue execution role is missing "
            "AWS Glue Data Quality permissions on the ruleset. Add "
            "`glue:GetDataQualityRuleset`, `glue:GetDataQualityRulesetEvaluationRun`, "
            "`glue:GetDataQualityResult`, and `glue:PublishDataQuality` on "
            "`arn:aws:glue:<region>:<account-id>:dataQualityRuleset/*` to the role "
            f"`{role}`. If the role is managed by this lab stack, run "
            "`bash scripts/deploy_infra.sh` to update the IAM policy, then rerun "
            "`bash scripts/run_glue_data_quality.sh`. Original AWS error: "
            f"{error}"
        )
    return f"Glue Data Quality run failed with status={status}: {run}"


def run_data_quality(wait: bool = True, poll_seconds: int = 20) -> Dict[str, object]:
    settings = get_settings()
    bucket = get_bucket_name(settings)
    database = get_glue_database_name(settings)
    role_arn = get_processing_role_arn(settings)
    ruleset_name = get_glue_data_quality_ruleset_name(settings)
    glue = client("glue", settings)
    s3 = client("s3", settings)

    s3.head_object(Bucket=bucket, Key=TARGET_KEY)
    sync_catalog_data(s3, bucket, [TARGET_TABLE])
    register_all_tables(glue, database, bucket)
    _ensure_ruleset(glue, ruleset_name, database)

    response = glue.start_data_quality_ruleset_evaluation_run(
        DataSource={"GlueTable": {"DatabaseName": database, "TableName": TARGET_TABLE}},
        Role=role_arn,
        NumberOfWorkers=settings.glue_data_quality_workers,
        Timeout=20,
        ClientToken=str(uuid.uuid4()),
        AdditionalRunOptions={
            "CloudWatchMetricsEnabled": False,
            "ResultsS3Prefix": f"s3://{bucket}/quality/aws_glue_data_quality/",
        },
        RulesetNames=[ruleset_name],
    )
    run_id = response["RunId"]
    print(f"Started Glue Data Quality evaluation run {run_id}")

    run = _wait_for_run(glue, run_id, poll_seconds) if wait else glue.get_data_quality_ruleset_evaluation_run(RunId=run_id)
    result_ids = run.get("ResultIds", [])
    results = [glue.get_data_quality_result(ResultId=result_id) for result_id in result_ids]
    report: Dict[str, object] = {
        "generated_at": utc_now_iso(),
        "ruleset_name": ruleset_name,
        "database": database,
        "table": TARGET_TABLE,
        "target_s3_key": TARGET_KEY,
        "run_id": run_id,
        "run": run,
        "results": results,
        "ruleset": FEATURES_TRAINING_RULESET,
        "results_s3_prefix": f"s3://{bucket}/quality/aws_glue_data_quality/",
    }
    write_json_to_s3(s3, report, bucket, "quality/glue_data_quality_result.json")
    print(f"Glue Data Quality report written to s3://{bucket}/quality/glue_data_quality_result.json")
    return report


def main() -> None:
    run_data_quality()


if __name__ == "__main__":
    main()
