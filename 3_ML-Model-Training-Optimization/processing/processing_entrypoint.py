from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, "/opt/ml/processing/lib")

from utils import (
    CATEGORICAL_FEATURES,
    ID_COLUMNS,
    NUMERIC_TRAINING_FEATURES,
    TARGET_COLUMN,
    ensure_dir,
    prepare_model_frame,
    write_json,
)


OFFLINE_STORE_SOURCES = {"offline_store", "offline-store"}
SNAPSHOT_SOURCES = {"snapshot", "feature_snapshot", "feature-snapshot"}
REQUIRED_OFFLINE_COLUMNS = ID_COLUMNS + NUMERIC_TRAINING_FEATURES + CATEGORICAL_FEATURES + [TARGET_COLUMN]


def find_input_file(input_path: Path) -> Path:
    if input_path.is_file():
        return input_path
    candidates = sorted(input_path.glob("*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No CSV input found under {input_path}")
    return candidates[0]


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Expected S3 URI, got {uri}")
    bucket, _, key = uri[5:].partition("/")
    return bucket, key


def _download_s3_file(s3_uri: str, local_path: Path, region_name: str) -> None:
    import boto3

    bucket, key = _parse_s3_uri(s3_uri)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    boto3.client("s3", region_name=region_name).download_file(bucket, key, str(local_path))


def _wait_for_athena_query(
    *,
    athena,
    query_execution_id: str,
    poll_seconds: int,
    max_wait_seconds: int,
) -> str:
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        response = athena.get_query_execution(QueryExecutionId=query_execution_id)
        status = response["QueryExecution"]["Status"]
        state = status["State"]
        if state == "SUCCEEDED":
            return response["QueryExecution"]["ResultConfiguration"]["OutputLocation"]
        if state in {"FAILED", "CANCELLED"}:
            reason = status.get("StateChangeReason", "No Athena failure reason returned.")
            raise RuntimeError(f"Athena query {query_execution_id} ended with {state}: {reason}")
        time.sleep(poll_seconds)
    raise TimeoutError(f"Timed out waiting for Athena query {query_execution_id}")


def _offline_store_query(database: str, table_name: str) -> str:
    columns = ", ".join(_quote_identifier(column) for column in REQUIRED_OFFLINE_COLUMNS)
    source = f"{_quote_identifier(database)}.{_quote_identifier(table_name)}"
    return f"""
WITH ranked_features AS (
    SELECT
        {columns},
        row_number() OVER (
            PARTITION BY {_quote_identifier("customer_id")}
            ORDER BY {_quote_identifier("event_time")} DESC
        ) AS row_num
    FROM {source}
    WHERE {_quote_identifier("customer_id")} IS NOT NULL
      AND {_quote_identifier("event_time")} IS NOT NULL
)
SELECT {columns}
FROM ranked_features
WHERE row_num = 1
""".strip()


def materialize_offline_store(
    *,
    feature_group_name: str,
    aws_region: str,
    athena_output_s3_uri: str,
    output_dir: Path,
    max_wait_seconds: int,
    poll_seconds: int,
) -> Path:
    import boto3

    if not feature_group_name:
        raise ValueError("--feature-group-name is required when --feature-source=offline_store")
    if not athena_output_s3_uri:
        raise ValueError("--athena-output-s3-uri is required when --feature-source=offline_store")

    sm = boto3.client("sagemaker", region_name=aws_region)
    athena = boto3.client("athena", region_name=aws_region)
    feature_group = sm.describe_feature_group(FeatureGroupName=feature_group_name)
    data_catalog = feature_group.get("OfflineStoreConfig", {}).get("DataCatalogConfig", {})
    database = data_catalog.get("Database")
    table_name = data_catalog.get("TableName")
    if not database or not table_name:
        raise RuntimeError(
            "Feature Group does not expose Offline Store DataCatalogConfig. "
            "Confirm Offline Store and Glue table creation are enabled."
        )

    query = _offline_store_query(database, table_name)
    deadline = time.time() + max_wait_seconds
    last_error: Exception | None = None
    attempt = 1
    while time.time() < deadline:
        try:
            response = athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": database},
                ResultConfiguration={"OutputLocation": athena_output_s3_uri},
            )
            query_execution_id = response["QueryExecutionId"]
            output_location = _wait_for_athena_query(
                athena=athena,
                query_execution_id=query_execution_id,
                poll_seconds=max(1, min(poll_seconds, 10)),
                max_wait_seconds=max(60, min(max_wait_seconds, 300)),
            )
            materialized_path = output_dir / "offline_store_features.csv"
            _download_s3_file(output_location, materialized_path, aws_region)
            df = pd.read_csv(materialized_path)
            if len(df) > 0:
                print(
                    "Materialized "
                    f"{len(df)} latest feature records from Feature Store Offline Store "
                    f"using Athena table {database}.{table_name}"
                )
                return materialized_path
            print(
                "Offline Store query returned 0 rows. "
                f"Waiting {poll_seconds}s before retry {attempt + 1}..."
            )
        except Exception as exc:  # Retry while Offline Store/Glue catches up.
            last_error = exc
            print(f"Offline Store materialization attempt {attempt} failed: {exc}")
        attempt += 1
        time.sleep(poll_seconds)

    raise TimeoutError(
        "Offline Store did not produce a usable training dataset before timeout. "
        f"Last error: {last_error}"
    )


def resolve_input_file(args: argparse.Namespace) -> tuple[Path, str]:
    source = args.feature_source.strip().lower()
    if source in OFFLINE_STORE_SOURCES:
        try:
            return (
                materialize_offline_store(
                    feature_group_name=args.feature_group_name,
                    aws_region=args.aws_region,
                    athena_output_s3_uri=args.athena_output_s3_uri,
                    output_dir=Path(args.input_data),
                    max_wait_seconds=args.offline_store_max_wait_seconds,
                    poll_seconds=args.offline_store_poll_seconds,
                ),
                "feature_store_offline_store",
            )
        except Exception:
            if not args.allow_snapshot_fallback:
                raise
            print("Falling back to feature snapshot CSV because Offline Store materialization failed.")
            return find_input_file(Path(args.input_data)), "feature_snapshot_fallback"
    if source in SNAPSHOT_SOURCES:
        return find_input_file(Path(args.input_data)), "feature_snapshot"
    raise ValueError(
        "--feature-source must be one of offline_store, offline-store, snapshot, feature_snapshot"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare train/validation/test datasets from churn features.")
    parser.add_argument("--input-data", default="/opt/ml/processing/input")
    parser.add_argument("--feature-source", default="offline_store")
    parser.add_argument("--feature-group-name", default="")
    parser.add_argument("--aws-region", default="us-east-1")
    parser.add_argument("--athena-output-s3-uri", default="")
    parser.add_argument("--offline-store-max-wait-seconds", type=int, default=900)
    parser.add_argument("--offline-store-poll-seconds", type=int, default=60)
    parser.add_argument("--allow-snapshot-fallback", action="store_true")
    parser.add_argument("--train-output", default="/opt/ml/processing/output/train")
    parser.add_argument("--validation-output", default="/opt/ml/processing/output/validation")
    parser.add_argument("--test-output", default="/opt/ml/processing/output/test")
    parser.add_argument("--metadata-output", default="/opt/ml/processing/output/metadata")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--validation-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    input_file, source_name = resolve_input_file(args)
    df = pd.read_csv(input_file)
    model_df, metadata = prepare_model_frame(df)

    train_validation, test = train_test_split(
        model_df,
        test_size=args.test_size,
        random_state=args.seed,
        stratify=model_df["churn_label"],
    )
    relative_validation_size = args.validation_size / (1.0 - args.test_size)
    train, validation = train_test_split(
        train_validation,
        test_size=relative_validation_size,
        random_state=args.seed,
        stratify=train_validation["churn_label"],
    )

    train_dir = ensure_dir(args.train_output)
    validation_dir = ensure_dir(args.validation_output)
    test_dir = ensure_dir(args.test_output)
    metadata_dir = ensure_dir(args.metadata_output)

    train.to_csv(train_dir / "train.csv", index=False)
    validation.to_csv(validation_dir / "validation.csv", index=False)
    test.to_csv(test_dir / "test.csv", index=False)

    metadata.update(
        {
            "input_rows": int(len(df)),
            "train_rows": int(len(train)),
            "validation_rows": int(len(validation)),
            "test_rows": int(len(test)),
            "source": source_name,
            "source_file": str(input_file),
            "feature_group_name": args.feature_group_name or None,
            "offline_store_materialization": source_name == "feature_store_offline_store",
        }
    )
    write_json(metadata, metadata_dir / "preprocessing_metadata.json")
    print(f"Prepared train={len(train)} validation={len(validation)} test={len(test)}")


if __name__ == "__main__":
    main()
