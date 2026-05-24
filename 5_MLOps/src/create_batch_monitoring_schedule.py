"""Create a SageMaker Model Monitor schedule for Batch Transform captures."""

from __future__ import annotations

import argparse
import json
import time

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    class ClientError(Exception):
        response = {"Error": {"Code": "Unknown"}}

from .aws_clients import create_clients
from .compute import select_instance_type
from .config import load_config, write_metadata
from .create_monitoring_schedule import model_monitor_image_uri, validate_monitoring_schedule_expression


RETRYABLE_CREATE_ERRORS = {
    "ConflictException",
    "InternalFailure",
    "ResourceInUse",
    "ResourceInUseException",
    "ThrottlingException",
    "TooManyRequestsException",
}


def _client_error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


def _client_error_details(exc: ClientError) -> dict[str, object]:
    metadata = exc.response.get("ResponseMetadata", {})
    return {
        "code": _client_error_code(exc),
        "message": exc.response.get("Error", {}).get("Message", ""),
        "request_id": metadata.get("RequestId", ""),
        "http_status_code": metadata.get("HTTPStatusCode", ""),
        "retry_attempts": metadata.get("RetryAttempts", ""),
    }


def _schedule_exists(clients, name: str) -> bool:
    try:
        clients.sagemaker.describe_monitoring_schedule(MonitoringScheduleName=name)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"ResourceNotFound", "ValidationException"}:
            return False
        raise


def _create_monitoring_schedule_with_retries(
    clients,
    request: dict[str, object],
    *,
    max_attempts: int = 3,
    poll_seconds: int = 15,
) -> dict[str, object]:
    name = str(request["MonitoringScheduleName"])
    for attempt in range(1, max_attempts + 1):
        try:
            return clients.sagemaker.create_monitoring_schedule(**request)
        except ClientError as exc:
            code = _client_error_code(exc)
            if code not in RETRYABLE_CREATE_ERRORS or attempt == max_attempts:
                raise
            print(
                f"CreateMonitoringSchedule for batch hit transient {code}; "
                f"waiting {poll_seconds}s before retry {attempt + 1}/{max_attempts}..."
            )
            time.sleep(poll_seconds)
    raise RuntimeError(f"Could not create batch monitoring schedule {name}.")


def _native_batch_schedule_unavailable_payload(
    *,
    config,
    image_uri: str,
    processing_compute,
    error: ClientError,
) -> dict[str, object]:
    payload = {
        "monitoring_schedule_name": config.batch_monitoring_schedule_name,
        "actual_monitoring_schedule_name": "",
        "status": "native_batch_schedule_unavailable",
        "batch_data_capture_s3_uri": config.batch_data_capture_s3_uri,
        "batch_transform_input_s3_uri": config.batch_transform_input_s3_uri,
        "monitoring_s3_uri": config.batch_monitoring_s3_uri,
        "statistics_s3_uri": config.statistics_s3_uri,
        "constraints_s3_uri": config.constraints_s3_uri,
        "cron": config.monitoring_cron_expression,
        "image_uri": image_uri,
        "compute_selection": processing_compute.to_dict(),
        "service_error": _client_error_details(error),
        "fallback_note": (
            "SageMaker CreateMonitoringSchedule returned repeated InternalFailure for BatchTransformInput. "
            "The lab can continue with the custom batch Data Quality fallback."
        ),
        "cost_warning": "No periodic native batch Model Monitor schedule was created.",
    }
    write_metadata(config, "batch_monitoring_schedule", payload)
    return payload


def create_batch_schedule() -> dict[str, object]:
    config = load_config(validate=True, require_execution_role=True)
    if not config.enable_model_monitor:
        payload = {"skipped": True, "reason": "ENABLE_MODEL_MONITOR=false"}
        write_metadata(config, "batch_monitoring_schedule", payload)
        return payload
    validate_monitoring_schedule_expression(config.monitoring_cron_expression)

    clients = create_clients(config)
    processing_compute = select_instance_type(
        config,
        workload="processing",
        preferred=config.model_monitor_processing_instance_type,
        candidates=config.model_monitor_processing_instance_type_candidates_list,
        session=clients.session,
    )
    if processing_compute.source == "fallback-no-positive-quota":
        raise RuntimeError("No SageMaker processing quota is available for batch monitoring schedule jobs.")

    image_uri = model_monitor_image_uri(config)
    if _schedule_exists(clients, config.batch_monitoring_schedule_name):
        payload = {
            "monitoring_schedule_name": config.batch_monitoring_schedule_name,
            "actual_monitoring_schedule_name": config.batch_monitoring_schedule_name,
            "status": "existing",
            "batch_data_capture_s3_uri": config.batch_data_capture_s3_uri,
            "monitoring_s3_uri": config.batch_monitoring_s3_uri,
            "statistics_s3_uri": config.statistics_s3_uri,
            "constraints_s3_uri": config.constraints_s3_uri,
        }
        write_metadata(config, "batch_monitoring_schedule", payload)
        return payload

    request = {
        "MonitoringScheduleName": config.batch_monitoring_schedule_name,
        "MonitoringScheduleConfig": {
            "ScheduleConfig": {"ScheduleExpression": config.monitoring_cron_expression},
            "MonitoringType": "DataQuality",
            "MonitoringJobDefinition": {
                "BaselineConfig": {
                    "StatisticsResource": {"S3Uri": config.statistics_s3_uri},
                    "ConstraintsResource": {"S3Uri": config.constraints_s3_uri},
                },
                "MonitoringInputs": [
                    {
                        "BatchTransformInput": {
                            "DataCapturedDestinationS3Uri": config.batch_data_capture_s3_uri,
                            "DatasetFormat": {"Json": {"Line": True}},
                            "LocalPath": "/opt/ml/processing/input/batch",
                            "S3InputMode": "File",
                            "S3DataDistributionType": "FullyReplicated",
                        }
                    }
                ],
                "MonitoringOutputConfig": {
                    "MonitoringOutputs": [
                        {
                            "S3Output": {
                                "S3Uri": config.batch_monitoring_s3_uri,
                                "LocalPath": "/opt/ml/processing/output",
                                "S3UploadMode": "EndOfJob",
                            }
                        }
                    ]
                },
                "MonitoringResources": {
                    "ClusterConfig": {
                        "InstanceCount": 1,
                        "InstanceType": processing_compute.selected_instance_type,
                        "VolumeSizeInGB": 20,
                    }
                },
                "MonitoringAppSpecification": {"ImageUri": image_uri},
                "StoppingCondition": {"MaxRuntimeInSeconds": 1800},
                "RoleArn": config.sagemaker_execution_role_arn,
            },
        },
        "Tags": config.tags,
    }
    try:
        response = _create_monitoring_schedule_with_retries(clients, request)
    except ClientError as exc:
        if _client_error_code(exc) == "InternalFailure":
            return _native_batch_schedule_unavailable_payload(
                config=config,
                image_uri=image_uri,
                processing_compute=processing_compute,
                error=exc,
            )
        raise
    payload = {
        "monitoring_schedule_name": config.batch_monitoring_schedule_name,
        "actual_monitoring_schedule_name": config.batch_monitoring_schedule_name,
        "status": "created",
        "batch_data_capture_s3_uri": config.batch_data_capture_s3_uri,
        "monitoring_s3_uri": config.batch_monitoring_s3_uri,
        "statistics_s3_uri": config.statistics_s3_uri,
        "constraints_s3_uri": config.constraints_s3_uri,
        "cron": config.monitoring_cron_expression,
        "image_uri": image_uri,
        "compute_selection": processing_compute.to_dict(),
        "service_response": response,
        "cost_warning": "Batch monitoring schedules create periodic processing jobs until deleted.",
    }
    write_metadata(config, "batch_monitoring_schedule", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(create_batch_schedule(), indent=2, default=str))


if __name__ == "__main__":
    main()
