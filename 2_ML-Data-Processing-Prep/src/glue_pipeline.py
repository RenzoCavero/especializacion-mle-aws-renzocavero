"""Entry point executed by AWS Glue Python Shell."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import boto3


def _parse_args(argv: list[str]) -> Dict[str, str]:
    args: Dict[str, str] = {}
    index = 0
    while index < len(argv):
        token = argv[index]
        if token.startswith("--"):
            key = token[2:]
            value = "true"
            if index + 1 < len(argv) and not argv[index + 1].startswith("--"):
                value = argv[index + 1]
                index += 1
            args[key] = value
        index += 1
    return args


def _ensure_project_package(s3_client, bucket_name: str) -> None:
    try:
        import src.pipeline  # noqa: F401
        return
    except ModuleNotFoundError as exc:
        if exc.name != "src":
            raise

    local_zip = Path("/tmp/ml_data_prep_src.zip")
    s3_client.download_file(bucket_name, "scripts/ml_data_prep_src.zip", str(local_zip))
    sys.path.insert(0, str(local_zip))


def main() -> None:
    args = _parse_args(sys.argv[1:])
    bucket_name = args["bucket-name"]
    database_name = args["database-name"]
    resource_prefix = args.get("resource-prefix", "ml-data-prep-lab")
    steps = args.get("pipeline-steps", "all")
    run_id = args.get("run-id") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    s3_client = boto3.client("s3")
    glue_client = boto3.client("glue")
    _ensure_project_package(s3_client, bucket_name)

    from src.pipeline import run_pipeline

    run_pipeline(
        s3_client=s3_client,
        glue_client=glue_client,
        bucket_name=bucket_name,
        database_name=database_name,
        resource_prefix=resource_prefix,
        steps=steps,
        run_id=run_id,
    )


if __name__ == "__main__":
    main()
