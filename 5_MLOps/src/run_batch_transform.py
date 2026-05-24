"""Run SageMaker Batch Transform with batch Data Capture enabled."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    class ClientError(Exception):
        response = {"Error": {"Code": "Unknown"}}

from .aws_clients import create_clients
from .compute import select_instance_type
from .config import load_config, write_metadata
from .deploy_model import _inference_environment, _upload_inference_source
from .resolve_approved_model import resolve_approved_model


def _exists(callable_obj, **kwargs) -> bool:
    try:
        callable_obj(**kwargs)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"ValidationException", "ResourceNotFound"}:
            return False
        raise


def _job_name(config) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{config.resource_prefix}-batch-{timestamp}"[:63].strip("-")


def ensure_batch_model(config, clients, approved: dict[str, object]) -> dict[str, object]:
    inference_source_s3_uri = _upload_inference_source(clients.s3, config)
    if _exists(clients.sagemaker.describe_model, ModelName=config.sagemaker_batch_model_name):
        return {
            "model_name": config.sagemaker_batch_model_name,
            "status": "existing",
            "inference_source_s3_uri": inference_source_s3_uri,
        }

    model_artifact_uri = str(approved.get("model_artifact_s3_uri") or "")
    image_uri = str(approved.get("image_uri") or config.model_image_uri or "")
    if not model_artifact_uri or not image_uri:
        raise ValueError("Batch Transform requires an approved model with ModelDataUrl and Image.")

    clients.sagemaker.create_model(
        ModelName=config.sagemaker_batch_model_name,
        ExecutionRoleArn=config.sagemaker_execution_role_arn,
        PrimaryContainer={
            "Image": image_uri,
            "ModelDataUrl": model_artifact_uri,
            "Environment": _inference_environment(config, inference_source_s3_uri),
        },
        Tags=config.tags,
    )
    return {
        "model_name": config.sagemaker_batch_model_name,
        "status": "created",
        "model_artifact_s3_uri": model_artifact_uri,
        "image_uri": image_uri,
        "inference_source_s3_uri": inference_source_s3_uri,
    }


def run_batch_transform(wait: bool = False, poll_seconds: int = 30) -> dict[str, object]:
    config = load_config(validate=True, require_execution_role=True)
    clients = create_clients(config)
    approved = resolve_approved_model()
    batch_compute = select_instance_type(
        config,
        workload="batch_transform",
        preferred=config.instance_type,
        candidates=config.batch_transform_instance_type_candidates_list,
        session=clients.session,
    )
    if batch_compute.source == "fallback-no-positive-quota":
        raise RuntimeError(
            "No SageMaker Batch Transform quota is available for the configured candidates. "
            "Run `python -m src.compute --workload batch-transform --inventory --limit 0`."
        )

    model_info = ensure_batch_model(config, clients, approved)
    job_name = _job_name(config)
    clients.sagemaker.create_transform_job(
        TransformJobName=job_name,
        ModelName=config.sagemaker_batch_model_name,
        MaxConcurrentTransforms=1,
        MaxPayloadInMB=1,
        BatchStrategy="SingleRecord",
        TransformInput={
            "DataSource": {
                "S3DataSource": {
                    "S3DataType": "S3Prefix",
                    "S3Uri": config.batch_transform_input_s3_uri,
                }
            },
            "ContentType": "application/json",
            "SplitType": "Line",
        },
        TransformOutput={
            "S3OutputPath": config.batch_transform_output_s3_uri,
            "Accept": "application/json",
            "AssembleWith": "Line",
        },
        DataCaptureConfig={
            "DestinationS3Uri": config.batch_data_capture_s3_uri,
            "GenerateInferenceId": True,
        },
        TransformResources={
            "InstanceType": batch_compute.selected_instance_type,
            "InstanceCount": 1,
        },
        Tags=config.tags,
    )

    description: dict[str, object] = {}
    if wait:
        while True:
            description = clients.sagemaker.describe_transform_job(TransformJobName=job_name)
            status = str(description.get("TransformJobStatus"))
            if status in {"Completed", "Failed", "Stopped"}:
                break
            print(f"Batch Transform job status: {status}. Waiting {poll_seconds}s...")
            time.sleep(poll_seconds)
        if description.get("TransformJobStatus") != "Completed":
            raise RuntimeError(
                f"Batch Transform job {job_name} ended with status "
                f"{description.get('TransformJobStatus')}: {description.get('FailureReason', '')}"
            )

    payload = {
        "transform_job_name": job_name,
        "model_info": model_info,
        "input_s3_uri": config.batch_transform_input_s3_uri,
        "output_s3_uri": config.batch_transform_output_s3_uri,
        "data_capture_s3_uri": config.batch_data_capture_s3_uri,
        "compute_selection": batch_compute.to_dict(),
        "description": description,
        "flow_note": (
            "Batch Transform has no persistent endpoint. Data Capture is configured on the transform job "
            "and writes captured inference data to S3 for batch Model Monitor."
        ),
    }
    write_metadata(config, "batch_transform", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(run_batch_transform(wait=args.wait, poll_seconds=args.poll_seconds), indent=2, default=str))


if __name__ == "__main__":
    main()
