"""Upload synthetic raw data and Glue job assets to S3."""

from __future__ import annotations

from pathlib import Path

from src.aws_clients import client, get_bucket_name
from src.config import SAMPLE_DATA_DIR, ensure_local_directories, get_settings
from src.generate_sample_data import write_sample_data
from src.glue_catalog import sync_catalog_data
from src.package_job_assets import upload_job_assets
from src.s3_io import ensure_prefixes, upload_file
from src.schemas import S3_ZONES


RAW_FILES = {
    "customers.csv": "raw/customers.csv",
    "transactions.csv": "raw/transactions.csv",
    "inference_transactions.csv": "raw/inference_transactions.csv",
}


def upload_raw_data(sample_dir: Path = SAMPLE_DATA_DIR) -> None:
    settings = get_settings()
    ensure_local_directories()
    missing = [name for name in RAW_FILES if not (sample_dir / name).exists()]
    if missing:
        print(f"Sample files missing {missing}; generating synthetic data first.")
        write_sample_data(sample_dir)

    bucket = get_bucket_name(settings)
    s3 = client("s3", settings)
    ensure_prefixes(s3, bucket, S3_ZONES)
    for filename, key in RAW_FILES.items():
        upload_file(s3, sample_dir / filename, bucket, key)
        print(f"Uploaded {sample_dir / filename} -> s3://{bucket}/{key}")
    synced = sync_catalog_data(
        s3,
        bucket,
        ["raw_customers", "raw_transactions", "raw_inference_transactions"],
    )
    if synced:
        print(f"Synced Athena-friendly raw copies: {', '.join(synced)}")
    upload_job_assets(bucket)


def main() -> None:
    upload_raw_data()


if __name__ == "__main__":
    main()
