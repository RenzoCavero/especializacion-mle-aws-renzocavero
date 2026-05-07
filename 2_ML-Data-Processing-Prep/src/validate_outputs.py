"""Validate that the cloud lab produced expected resources and S3 outputs."""

from __future__ import annotations

from src.aws_clients import client, get_bucket_name, get_glue_database_name
from src.config import get_settings
from src.glue_catalog import TABLES


EXPECTED_KEYS = [
    "raw/customers.csv",
    "raw/transactions.csv",
    "raw/inference_transactions.csv",
    "profiles/profile.json",
    "quality/quality_report.json",
    "cleaned/customers.csv",
    "cleaned/transactions.csv",
    "curated/customer_transactions.csv",
    "features/training_features.csv",
    "features/inference_features.csv",
    "features/training_dataset.csv",
    "inference/inference_dataset.csv",
    "lineage/lineage.json",
    "lineage/lineage.md",
    "reports/dataset_card.json",
    "reports/dataset_card.md",
    "logs/pipeline_run.json",
]


def _object_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def validate_outputs() -> None:
    settings = get_settings()
    bucket = get_bucket_name(settings)
    database = get_glue_database_name(settings)
    s3 = client("s3", settings)
    glue = client("glue", settings)

    missing = [key for key in EXPECTED_KEYS if not _object_exists(s3, bucket, key)]
    missing_tables = []
    for table_name in TABLES:
        try:
            glue.get_table(DatabaseName=database, Name=table_name)
        except Exception:
            missing_tables.append(table_name)

    if missing or missing_tables:
        raise RuntimeError(
            f"Validation failed. Missing S3 keys={missing}. Missing Glue tables={missing_tables}."
        )

    print("Validation passed.")
    print(f"S3 bucket: s3://{bucket}/")
    print(f"Glue database: {database}")
    print(f"Validated {len(EXPECTED_KEYS)} S3 objects and {len(TABLES)} Glue tables.")


def main() -> None:
    validate_outputs()


if __name__ == "__main__":
    main()
