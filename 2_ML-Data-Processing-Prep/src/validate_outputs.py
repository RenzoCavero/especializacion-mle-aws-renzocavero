"""Validate that the cloud lab produced expected resources and S3 outputs."""

from __future__ import annotations

from src.aws_clients import client, get_bucket_name, get_glue_database_name
from src.config import get_settings
from src.glue_catalog import TABLES, catalog_location, catalog_object_key


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


EXPECTED_CATALOG_KEYS = [catalog_object_key(table_name) for table_name in TABLES]


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

    all_expected_keys = EXPECTED_KEYS + EXPECTED_CATALOG_KEYS
    missing = [key for key in all_expected_keys if not _object_exists(s3, bucket, key)]
    missing_tables = []
    location_mismatches = []
    for table_name in TABLES:
        try:
            table = glue.get_table(DatabaseName=database, Name=table_name)["Table"]
        except Exception:
            missing_tables.append(table_name)
            continue
        actual_location = table["StorageDescriptor"].get("Location", "")
        expected_location = catalog_location(table_name, bucket)
        if f"{actual_location.rstrip('/')}/" != expected_location:
            location_mismatches.append(
                {
                    "table": table_name,
                    "actual": actual_location,
                    "expected": expected_location,
                }
            )

    if missing or missing_tables or location_mismatches:
        raise RuntimeError(
            "Validation failed. "
            f"Missing S3 keys={missing}. "
            f"Missing Glue tables={missing_tables}. "
            f"Glue table location mismatches={location_mismatches}."
        )

    print("Validation passed.")
    print(f"S3 bucket: s3://{bucket}/")
    print(f"Glue database: {database}")
    print(f"Validated {len(all_expected_keys)} S3 objects and {len(TABLES)} Glue tables.")


def main() -> None:
    validate_outputs()


if __name__ == "__main__":
    main()
