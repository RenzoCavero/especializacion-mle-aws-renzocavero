from __future__ import annotations

import argparse
from typing import Any

from .aws_clients import client_error_code, clients
from .config import load_config, parse_s3_uri, read_json, utc_now, write_json


def is_lab_s3_uri(config, uri: str) -> bool:
    try:
        bucket, key = parse_s3_uri(uri)
    except Exception:
        return False
    return bucket == config.s3_bucket_name and key.startswith(config.s3_prefix.strip("/") + "/")


def _delete_s3_prefix(s3: Any, bucket: str, prefix: str) -> int:
    deleted = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix.rstrip("/") + "/"):
        objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if objects:
            s3.delete_objects(Bucket=bucket, Delete={"Objects": objects})
            deleted += len(objects)
    return deleted


def cleanup_batch_resources(delete_s3: bool = False) -> dict[str, Any]:
    config = load_config(require_aws=True)
    aws = clients(config)
    sagemaker = aws.sagemaker
    actions: list[str] = []
    batch = read_json(config.metadata_path("batch_transform_job.json"), default={})

    job_name = batch.get("transform_job_name")
    if job_name:
        try:
            description = sagemaker.describe_transform_job(TransformJobName=job_name)
            if description.get("TransformJobStatus") in {"InProgress", "Stopping"}:
                sagemaker.stop_transform_job(TransformJobName=job_name)
                actions.append(f"stop_transform_job:{job_name}")
            else:
                actions.append(f"preserve_completed_transform_job:{job_name}")
        except Exception as exc:
            if client_error_code(exc) not in {"ValidationException", "ResourceNotFound"}:
                raise

    deleted_objects = 0
    if delete_s3 or config.delete_lab_s3:
        for uri in (batch.get("batch_input_s3_uri"), batch.get("batch_output_s3_uri")):
            if uri and is_lab_s3_uri(config, uri):
                bucket, key = parse_s3_uri(uri)
                deleted_objects += _delete_s3_prefix(aws.s3, bucket, key)
                actions.append(f"delete_s3_prefix:{uri}")

    metadata = {
        "actions": actions,
        "deleted_s3_objects": deleted_objects,
        "delete_s3_requested": bool(delete_s3 or config.delete_lab_s3),
        "note": "SageMaker Transform Jobs historicos no se eliminan; solo se detienen si estan activos.",
        "completed_at": utc_now(),
    }
    write_json(config.metadata_path("cleanup_batch.json"), metadata)
    print("Cleanup batch completado.")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup seguro de recursos batch.")
    parser.add_argument("--delete-s3", action="store_true", help="Borrar prefijos S3 del laboratorio.")
    args = parser.parse_args()
    cleanup_batch_resources(delete_s3=args.delete_s3)


if __name__ == "__main__":
    main()
