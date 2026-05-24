"""Package and upload Glue job assets to S3."""

from __future__ import annotations

import zipfile
from pathlib import Path

from src.aws_clients import client, get_bucket_name
from src.config import LOCAL_CACHE_DIR, PROJECT_ROOT, get_settings
from src.s3_io import upload_file


ZIP_NAME = "ml_data_prep_src.zip"


def build_source_zip(output_path: Path = LOCAL_CACHE_DIR / ZIP_NAME) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    src_dir = PROJECT_ROOT / "src"
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in src_dir.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            archive.write(path, path.relative_to(PROJECT_ROOT).as_posix())
    return output_path


def upload_job_assets(bucket_name: str | None = None) -> None:
    settings = get_settings()
    bucket = bucket_name or get_bucket_name(settings)
    s3 = client("s3", settings)
    zip_path = build_source_zip()
    upload_file(s3, zip_path, bucket, f"scripts/{ZIP_NAME}")
    upload_file(s3, PROJECT_ROOT / "src" / "glue_pipeline.py", bucket, "scripts/glue_pipeline.py")
    print(f"Uploaded Glue assets to s3://{bucket}/scripts/")


def main() -> None:
    upload_job_assets()


if __name__ == "__main__":
    main()

