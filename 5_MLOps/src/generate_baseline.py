"""Create a SageMaker Model Monitor baseline job."""

from __future__ import annotations

import argparse
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .aws_clients import create_clients
from .compute import select_instance_type
from .config import load_config, write_metadata
from .create_monitoring_schedule import model_monitor_image_uri
from .generate_sample_data import FEATURE_COLUMNS


MONITOR_COLUMNS = ["record_id", *FEATURE_COLUMNS]


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    bucket_key = uri[5:]
    bucket, _, key = bucket_key.partition("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI without bucket/key: {uri}")
    return bucket, key


def _job_name(config) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    base = f"{config.resource_prefix}-baseline-{timestamp}"
    return base[:63].strip("-")


def _read_baseline_frame(clients, config) -> pd.DataFrame:
    local_path = config.local_cache_dir / "baseline.csv"
    if local_path.exists():
        return pd.read_csv(local_path)

    bucket, key = _parse_s3_uri(config.baseline_data_s3_uri)
    response = clients.s3.get_object(Bucket=bucket, Key=key)
    return pd.read_csv(io.BytesIO(response["Body"].read()))


def _prepare_model_monitor_baseline(clients, config) -> tuple[str, list[str]]:
    frame = _read_baseline_frame(clients, config)
    missing = [column for column in MONITOR_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Baseline dataset is missing required feature columns: {', '.join(missing)}")
    monitor_frame = frame[[*MONITOR_COLUMNS]].copy()
    destination = f"{config.raw_data_s3_uri}/baseline_monitor.csv"
    bucket, key = _parse_s3_uri(destination)
    payload = monitor_frame.to_csv(index=False).encode("utf-8")
    clients.s3.put_object(Bucket=bucket, Key=key, Body=payload, ContentType="text/csv")
    return destination, list(monitor_frame.columns)


def _validate_model_monitor_baseline_artifacts(clients, config) -> dict[str, object]:
    constraints_bucket, constraints_key = _parse_s3_uri(config.constraints_s3_uri)
    statistics_bucket, statistics_key = _parse_s3_uri(config.statistics_s3_uri)
    constraints = json.loads(
        clients.s3.get_object(Bucket=constraints_bucket, Key=constraints_key)["Body"].read().decode("utf-8")
    )
    statistics = json.loads(
        clients.s3.get_object(Bucket=statistics_bucket, Key=statistics_key)["Body"].read().decode("utf-8")
    )
    version = constraints.get("version")
    features = constraints.get("features")
    if not isinstance(version, (int, float)) or not isinstance(features, list):
        raise RuntimeError(
            "Generated constraints.json is not compatible with SageMaker Model Monitor analyzer. "
            "Expected numeric `version` and list `features`."
        )
    return {
        "constraints_version": version,
        "constraints_feature_count": len(features),
        "statistics_has_features": isinstance(statistics.get("features"), list),
    }


def generate_baseline(wait: bool = False, poll_seconds: int = 30, timeout_seconds: int = 2400) -> dict[str, object]:
    config = load_config(validate=True, require_execution_role=True)
    if poll_seconds <= 0:
        raise ValueError("--poll-seconds must be greater than 0")
    if not config.enable_model_monitor:
        payload = {"skipped": True, "reason": "ENABLE_MODEL_MONITOR=false"}
        write_metadata(config, "baseline", payload)
        return payload

    clients = create_clients(config)
    processing_compute = select_instance_type(
        config,
        workload="processing",
        preferred=config.model_monitor_processing_instance_type,
        candidates=config.model_monitor_processing_instance_type_candidates_list,
        session=clients.session,
    )
    if processing_compute.source == "fallback-no-positive-quota":
        raise RuntimeError(
            "No SageMaker processing quota is available for baseline generation. "
            "Run `python -m src.compute --workload processing --inventory --limit 0`."
        )

    baseline_monitor_s3_uri, baseline_columns = _prepare_model_monitor_baseline(clients, config)
    job_name = _job_name(config)
    image_uri = model_monitor_image_uri(config)
    clients.sagemaker.create_processing_job(
        ProcessingJobName=job_name,
        RoleArn=config.sagemaker_execution_role_arn,
        AppSpecification={
            "ImageUri": image_uri,
        },
        Environment={
            "dataset_format": json.dumps({"csv": {"header": True}}),
            "dataset_source": "/opt/ml/processing/sm_input",
            "output_path": "/opt/ml/processing/sm_output",
            "publish_cloudwatch_metrics": "Disabled",
        },
        ProcessingResources={
            "ClusterConfig": {
                "InstanceCount": 1,
                "InstanceType": processing_compute.selected_instance_type,
                "VolumeSizeInGB": 20,
            }
        },
        ProcessingInputs=[
            {
                "InputName": "baseline-data",
                "S3Input": {
                    "S3Uri": baseline_monitor_s3_uri,
                    "LocalPath": "/opt/ml/processing/sm_input",
                    "S3DataType": "S3Prefix",
                    "S3InputMode": "File",
                    "S3DataDistributionType": "FullyReplicated",
                    "S3CompressionType": "None",
                },
            },
        ],
        ProcessingOutputConfig={
            "Outputs": [
                {
                    "OutputName": "baseline",
                    "S3Output": {
                        "S3Uri": config.baseline_s3_uri,
                        "LocalPath": "/opt/ml/processing/sm_output",
                        "S3UploadMode": "EndOfJob",
                    },
                }
            ]
        },
        StoppingCondition={"MaxRuntimeInSeconds": 1800},
        Tags=config.tags,
    )

    description: dict[str, object] = {}
    artifact_validation: dict[str, object] = {}
    if wait:
        started_at = time.monotonic()
        print(
            "Baseline processing job started: "
            f"{job_name} on {processing_compute.selected_instance_type}. "
            f"Local wait timeout: {timeout_seconds}s."
        )
        while True:
            description = clients.sagemaker.describe_processing_job(ProcessingJobName=job_name)
            status = str(description.get("ProcessingJobStatus"))
            if status in {"Completed", "Failed", "Stopped"}:
                break
            elapsed_seconds = int(time.monotonic() - started_at)
            if timeout_seconds > 0 and elapsed_seconds >= timeout_seconds:
                raise TimeoutError(
                    f"Baseline processing job {job_name} is still {status} after {elapsed_seconds}s. "
                    "The AWS job may still be running. Check it with "
                    f"`aws sagemaker describe-processing-job --processing-job-name {job_name}` or stop it with "
                    f"`aws sagemaker stop-processing-job --processing-job-name {job_name}`."
                )
            print(f"Baseline processing job status: {status}. Waiting {poll_seconds}s...")
            time.sleep(poll_seconds)
        if description.get("ProcessingJobStatus") != "Completed":
            raise RuntimeError(
                f"Baseline processing job {job_name} ended with status "
                f"{description.get('ProcessingJobStatus')}: {description.get('FailureReason', '')}"
            )
        artifact_validation = _validate_model_monitor_baseline_artifacts(clients, config)

    payload = {
        "baseline_job_name": job_name,
        "baseline_job_type": "SageMaker Model Monitor analyzer Processing Job",
        "baseline_dataset": baseline_monitor_s3_uri,
        "baseline_columns": baseline_columns,
        "baseline_s3_uri": config.baseline_s3_uri,
        "statistics_s3_uri": config.statistics_s3_uri,
        "constraints_s3_uri": config.constraints_s3_uri,
        "image_uri": image_uri,
        "compute_selection": processing_compute.to_dict(),
        "artifact_validation": artifact_validation,
        "processing_job_description": description,
        "cost_warning": "Model Monitor baseline jobs generate SageMaker Processing cost.",
        "sdk_note": "Uses the prebuilt Model Monitor analyzer image through boto3 low-level APIs for SageMaker Python SDK v3 compatibility.",
    }
    write_metadata(config, "baseline", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=int, default=2400)
    args = parser.parse_args()
    print(
        json.dumps(
            generate_baseline(
                wait=args.wait,
                poll_seconds=args.poll_seconds,
                timeout_seconds=args.timeout_seconds,
            ),
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
