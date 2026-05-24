"""Upload local lab datasets to S3."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .aws_clients import create_clients
from .config import load_config, write_metadata


def upload_directory(local_dir: Path, bucket: str, prefix: str) -> dict[str, str]:
    config = load_config(validate=True)
    clients = create_clients(config)
    uploaded: dict[str, str] = {}
    for path in sorted(local_dir.glob("*")):
        if path.is_file() and path.name != ".gitkeep":
            key = f"{prefix.rstrip('/')}/{path.name}"
            clients.s3.upload_file(str(path), bucket, key)
            uploaded[path.name] = f"s3://{bucket}/{key}"
    return uploaded


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload generated sample data to S3.")
    parser.add_argument("--local-dir", default="data/local_cache")
    parser.add_argument("--s3-prefix", default="")
    args = parser.parse_args()

    config = load_config(validate=True)
    prefix = args.s3_prefix or f"{config.resource_prefix}/{config.environment}/data/raw"
    uploaded = upload_directory(Path(args.local_dir), config.s3_bucket_name, prefix)
    write_metadata(config, "data_upload", {"uploaded": uploaded})
    print(json.dumps(uploaded, indent=2))


if __name__ == "__main__":
    main()
