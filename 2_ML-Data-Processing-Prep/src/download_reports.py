"""Download report artifacts from S3 to artifacts/local_outputs."""

from __future__ import annotations

from src.aws_clients import client, get_bucket_name
from src.config import LOCAL_OUTPUTS_DIR, ensure_local_directories, get_settings
from src.s3_io import download_prefix


REPORT_PREFIXES = ["profiles/", "quality/", "lineage/", "reports/", "logs/"]


def download_reports() -> None:
    settings = get_settings()
    ensure_local_directories()
    bucket = get_bucket_name(settings)
    s3 = client("s3", settings)
    total = 0
    for prefix in REPORT_PREFIXES:
        count = download_prefix(s3, bucket, prefix, LOCAL_OUTPUTS_DIR)
        total += count
        print(f"Downloaded {count} objects from s3://{bucket}/{prefix}")
    print(f"Reports downloaded to {LOCAL_OUTPUTS_DIR} ({total} files).")


def main() -> None:
    download_reports()


if __name__ == "__main__":
    main()

