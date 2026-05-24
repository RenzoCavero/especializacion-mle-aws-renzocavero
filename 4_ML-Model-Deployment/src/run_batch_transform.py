from __future__ import annotations

import argparse

from .aws_clients import client_error_code, clients
from .config import load_config, read_json, timestamp_slug, utc_now, write_json


def run_batch_transform(wait: bool | None = None) -> dict[str, object]:
    config = load_config(require_aws=True)
    model_metadata = read_json(config.metadata_path("sagemaker_model.json"))
    input_metadata = read_json(config.metadata_path("batch_input.json"))
    aws = clients(config)
    sagemaker = aws.sagemaker

    job_name = f"{config.batch_job_prefix}-{timestamp_slug()}"[:63].strip("-")
    output_s3_uri = config.s3_uri("batch", "output", job_name)
    wait = config.wait_for_batch if wait is None else wait

    request = {
        "TransformJobName": job_name,
        "ModelName": model_metadata["model_name"],
        "TransformInput": {
            "DataSource": {
                "S3DataSource": {
                    "S3DataType": "S3Prefix",
                    "S3Uri": input_metadata["batch_input_s3_uri"],
                }
            },
            "ContentType": "text/csv",
            "SplitType": config.split_type,
        },
        "TransformOutput": {
            "S3OutputPath": output_s3_uri,
            "Accept": "application/json",
        },
        "TransformResources": {
            "InstanceType": config.batch_instance_type,
            "InstanceCount": config.batch_instance_count,
        },
        "BatchStrategy": config.batch_strategy,
        "MaxPayloadInMB": config.max_payload_mb,
        "MaxConcurrentTransforms": config.max_concurrent_transforms,
        "Tags": config.tags,
    }
    sagemaker.create_transform_job(**request)
    status = "Submitted"
    description = {"TransformJobStatus": status}
    if wait:
        waiter = sagemaker.get_waiter("transform_job_completed_or_stopped")
        waiter.wait(TransformJobName=job_name)
        description = sagemaker.describe_transform_job(TransformJobName=job_name)
        status = description.get("TransformJobStatus", status)

    metadata = {
        "transform_job_name": job_name,
        "model_name": model_metadata["model_name"],
        "batch_input_s3_uri": input_metadata["batch_input_s3_uri"],
        "batch_output_s3_uri": output_s3_uri,
        "status": status,
        "waited": wait,
        "split_type": config.split_type,
        "batch_strategy": config.batch_strategy,
        "max_payload_mb": config.max_payload_mb,
        "max_concurrent_transforms": config.max_concurrent_transforms,
        "instance_type": config.batch_instance_type,
        "instance_count": config.batch_instance_count,
        "created_at": utc_now(),
        "description": description,
    }
    write_json(config.metadata_path("batch_transform_job.json"), metadata)
    print(f"SageMaker Batch Transform Job: {job_name} ({status})")
    print(f"Output S3: {output_s3_uri}")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecutar SageMaker Batch Transform Job.")
    parser.add_argument("--no-wait", action="store_true", help="No esperar finalizacion del job.")
    args = parser.parse_args()
    try:
        run_batch_transform(wait=not args.no_wait)
    except Exception as exc:
        if client_error_code(exc) in {"AccessDenied", "AccessDeniedException"}:
            raise SystemExit("Permisos insuficientes para ejecutar Batch Transform.") from exc
        raise


if __name__ == "__main__":
    main()
