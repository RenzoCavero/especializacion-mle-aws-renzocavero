"""Run optional AWS Glue Data Catalog column statistics for a catalog table."""

from __future__ import annotations

import time
from typing import Any, Dict

from src.aws_clients import client, get_bucket_name, get_glue_database_name, get_processing_role_arn
from src.config import get_settings
from src.data_utils import utc_now_iso
from src.glue_catalog import register_all_tables, sync_catalog_data
from src.s3_io import write_json_to_s3


TARGET_TABLE = "features_training"
TARGET_KEY = "features/training_dataset.csv"
COLUMN_NAMES = [
    "amount",
    "amount_log",
    "customer_txn_count",
    "amount_to_customer_avg",
    "is_fraud",
    "split",
]


def _find_task_run(glue_client: Any, database_name: str, table_name: str, run_id: str) -> Dict[str, object]:
    response = glue_client.get_column_statistics_task_runs(DatabaseName=database_name, TableName=table_name, MaxResults=25)
    for run in response.get("ColumnStatisticsTaskRuns", []):
        if run.get("ColumnStatisticsTaskRunId") == run_id:
            return run
    return {"ColumnStatisticsTaskRunId": run_id, "Status": "UNKNOWN"}


def _wait_for_task(glue_client: Any, database_name: str, table_name: str, run_id: str, poll_seconds: int) -> Dict[str, object]:
    while True:
        run = _find_task_run(glue_client, database_name, table_name, run_id)
        status = run.get("Status", "UNKNOWN")
        print(f"Glue column statistics task state: {status}")
        if status in {"SUCCEEDED", "FAILED", "STOPPED"}:
            if status != "SUCCEEDED":
                raise RuntimeError(_format_column_statistics_failure(status, run))
            return run
        time.sleep(poll_seconds)


def _format_column_statistics_failure(status: str, details: object) -> str:
    message = str(details)
    if "Unable to Validate access to underlying S3 path" in message or "AccessDeniedException" in message:
        return (
            "Glue Column Statistics failed because the role used for the task cannot validate "
            "or read the S3 location of the Glue table. The role needs `s3:ListBucket` on "
            "the lab bucket and `s3:GetObject` on the table data objects. If the role is "
            "managed by this lab stack, run `bash scripts/deploy_infra.sh` to update the "
            "IAM policy, then rerun `bash scripts/run_glue_column_statistics.sh`. "
            f"Original AWS error: {message}"
        )
    return f"Glue column statistics task failed with status={status}: {details}"


def run_column_statistics(wait: bool = True, poll_seconds: int = 20) -> Dict[str, object]:
    settings = get_settings()
    bucket = get_bucket_name(settings)
    database = get_glue_database_name(settings)
    role_arn = get_processing_role_arn(settings)
    glue = client("glue", settings)
    s3 = client("s3", settings)

    s3.head_object(Bucket=bucket, Key=TARGET_KEY)
    sync_catalog_data(s3, bucket, [TARGET_TABLE])
    register_all_tables(glue, database, bucket)

    try:
        response = glue.start_column_statistics_task_run(
            DatabaseName=database,
            TableName=TARGET_TABLE,
            ColumnNameList=COLUMN_NAMES,
            Role=role_arn,
            SampleSize=100.0,
        )
    except Exception as exc:
        raise RuntimeError(_format_column_statistics_failure("FAILED", exc)) from exc
    run_id = response["ColumnStatisticsTaskRunId"]
    print(f"Started Glue column statistics task {run_id}")

    task_run = _wait_for_task(glue, database, TARGET_TABLE, run_id, poll_seconds) if wait else _find_task_run(
        glue,
        database,
        TARGET_TABLE,
        run_id,
    )
    statistics = glue.get_column_statistics_for_table(
        DatabaseName=database,
        TableName=TARGET_TABLE,
        ColumnNames=COLUMN_NAMES,
    )
    report: Dict[str, object] = {
        "generated_at": utc_now_iso(),
        "database": database,
        "table": TARGET_TABLE,
        "target_s3_key": TARGET_KEY,
        "column_names": COLUMN_NAMES,
        "task_run": task_run,
        "statistics": statistics,
    }
    write_json_to_s3(s3, report, bucket, "profiles/glue_column_statistics_features_training.json")
    print(
        "Glue column statistics report written to "
        f"s3://{bucket}/profiles/glue_column_statistics_features_training.json"
    )
    return report


def main() -> None:
    run_column_statistics()


if __name__ == "__main__":
    main()
