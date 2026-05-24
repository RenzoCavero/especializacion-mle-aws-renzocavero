"""Create a native SageMaker Model Quality Monitor schedule."""

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
from .config import load_config, read_metadata, write_metadata
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


def _client_error_message(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Message", ""))


def _client_error_details(exc: ClientError) -> dict[str, object]:
    metadata = exc.response.get("ResponseMetadata", {})
    return {
        "code": _client_error_code(exc),
        "message": _client_error_message(exc),
        "request_id": metadata.get("RequestId", ""),
        "http_status_code": metadata.get("HTTPStatusCode", ""),
        "retry_attempts": metadata.get("RetryAttempts", ""),
    }


def _describe_schedule(clients, name: str) -> dict[str, object] | None:
    try:
        return clients.sagemaker.describe_monitoring_schedule(MonitoringScheduleName=name)
    except ClientError as exc:
        if _client_error_code(exc) in {"ResourceNotFound", "ValidationException"}:
            return None
        raise


def _describe_job_definition(clients, name: str) -> dict[str, object] | None:
    try:
        return clients.sagemaker.describe_model_quality_job_definition(JobDefinitionName=name)
    except ClientError as exc:
        if _client_error_code(exc) in {"ResourceNotFound", "ValidationException"}:
            return None
        raise


def _wait_for_schedule_deleted(clients, name: str, poll_seconds: int = 15) -> None:
    while True:
        description = _describe_schedule(clients, name)
        if description is None:
            return
        status = description.get("MonitoringScheduleStatus", "Deleting")
        print(f"Model quality schedule {name} is {status}. Waiting {poll_seconds}s...")
        time.sleep(poll_seconds)


def _delete_job_definition_if_exists(clients, name: str) -> None:
    if _describe_job_definition(clients, name) is None:
        return
    clients.sagemaker.delete_model_quality_job_definition(JobDefinitionName=name)


def _fallback_schedule_name(base_name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = f"-{timestamp}"
    return f"{base_name[: 63 - len(suffix)].strip('-')}{suffix}"


def _endpoint_capture_modes(clients, endpoint_name: str) -> list[str]:
    endpoint = clients.sagemaker.describe_endpoint(EndpointName=endpoint_name)
    endpoint_config = clients.sagemaker.describe_endpoint_config(EndpointConfigName=endpoint["EndpointConfigName"])
    capture = endpoint_config.get("DataCaptureConfig", {})
    return sorted(
        str(item.get("CaptureMode"))
        for item in capture.get("CaptureOptions", [])
        if isinstance(item, dict) and item.get("CaptureMode")
    )


def _json_or_column_attribute(attribute: str) -> str:
    value = str(attribute).strip()
    if not value or value.startswith("$.") or value.isdigit():
        return value
    return f"$.{value}"


def _model_quality_job_definition_request(
    *,
    config,
    image_uri: str,
    instance_type: str,
) -> dict[str, object]:
    return {
        "JobDefinitionName": config.model_quality_job_definition_name,
        "ModelQualityAppSpecification": {
            "ImageUri": image_uri,
            "ProblemType": config.model_quality_problem_type,
            "Environment": {
                "publish_cloudwatch_metrics": "Enabled",
            },
        },
        "ModelQualityBaselineConfig": {
            "ConstraintsResource": {"S3Uri": config.model_quality_constraints_s3_uri},
        },
        "ModelQualityJobInput": {
            "EndpointInput": {
                "EndpointName": config.endpoint_name,
                "LocalPath": "/opt/ml/processing/input/endpoint",
                "S3InputMode": "File",
                "S3DataDistributionType": "FullyReplicated",
                "InferenceAttribute": _json_or_column_attribute(config.model_quality_inference_attribute),
                "ProbabilityAttribute": _json_or_column_attribute(config.model_quality_probability_attribute),
                "StartTimeOffset": config.model_quality_start_time_offset,
                "EndTimeOffset": config.model_quality_end_time_offset,
            },
            "GroundTruthS3Input": {"S3Uri": config.model_quality_ground_truth_s3_uri},
        },
        "ModelQualityJobOutputConfig": {
            "MonitoringOutputs": [
                {
                    "S3Output": {
                        "S3Uri": config.model_quality_reports_s3_uri,
                        "LocalPath": "/opt/ml/processing/output",
                        "S3UploadMode": "EndOfJob",
                    }
                }
            ]
        },
        "JobResources": {
            "ClusterConfig": {
                "InstanceCount": 1,
                "InstanceType": instance_type,
                "VolumeSizeInGB": 20,
            }
        },
        "RoleArn": config.sagemaker_execution_role_arn,
        "StoppingCondition": {"MaxRuntimeInSeconds": 1800},
        "Tags": config.tags,
    }


def _model_quality_monitoring_definition(
    *,
    config,
    image_uri: str,
    instance_type: str,
    baseline_metadata: dict[str, object],
) -> dict[str, object]:
    baseline_config: dict[str, object] = {
        "StatisticsResource": {"S3Uri": config.model_quality_statistics_s3_uri},
        "ConstraintsResource": {"S3Uri": config.model_quality_constraints_s3_uri},
    }
    baseline_job_name = str(baseline_metadata.get("baseline_job_name") or "")
    if baseline_job_name:
        baseline_config["BaseliningJobName"] = baseline_job_name
    return {
        "BaselineConfig": baseline_config,
        "Environment": {
            "publish_cloudwatch_metrics": "Enabled",
            "problem_type": config.model_quality_problem_type,
            "ground_truth_input": config.model_quality_ground_truth_s3_uri,
        },
        "MonitoringInputs": [
            {
                "EndpointInput": {
                    "EndpointName": config.endpoint_name,
                    "LocalPath": "/opt/ml/processing/input/endpoint",
                    "S3InputMode": "File",
                    "S3DataDistributionType": "FullyReplicated",
                    "InferenceAttribute": _json_or_column_attribute(config.model_quality_inference_attribute),
                    "ProbabilityAttribute": _json_or_column_attribute(config.model_quality_probability_attribute),
                    "StartTimeOffset": config.model_quality_start_time_offset,
                    "EndTimeOffset": config.model_quality_end_time_offset,
                }
            }
        ],
        "MonitoringOutputConfig": {
            "MonitoringOutputs": [
                {
                    "S3Output": {
                        "S3Uri": config.model_quality_reports_s3_uri,
                        "LocalPath": "/opt/ml/processing/output",
                        "S3UploadMode": "EndOfJob",
                    }
                }
            ]
        },
        "MonitoringResources": {
            "ClusterConfig": {
                "InstanceCount": 1,
                "InstanceType": instance_type,
                "VolumeSizeInGB": 20,
            }
        },
        "MonitoringAppSpecification": {"ImageUri": image_uri},
        "StoppingCondition": {"MaxRuntimeInSeconds": 1800},
        "RoleArn": config.sagemaker_execution_role_arn,
    }


def _inline_schedule_request(
    *,
    config,
    image_uri: str,
    instance_type: str,
    baseline_metadata: dict[str, object],
    schedule_name: str,
) -> dict[str, object]:
    return {
        "MonitoringScheduleName": schedule_name,
        "MonitoringScheduleConfig": {
            "ScheduleConfig": {"ScheduleExpression": config.model_quality_monitoring_cron_expression},
            "MonitoringJobDefinition": _model_quality_monitoring_definition(
                config=config,
                image_uri=image_uri,
                instance_type=instance_type,
                baseline_metadata=baseline_metadata,
            ),
            "MonitoringType": "ModelQuality",
        },
        "Tags": config.tags,
    }


def _existing_schedule_matches(description: dict[str, object], *, config) -> bool:
    schedule_config = description.get("MonitoringScheduleConfig", {})
    if not isinstance(schedule_config, dict):
        return False
    if schedule_config.get("MonitoringType") != "ModelQuality":
        return False
    if schedule_config.get("ScheduleConfig", {}).get("ScheduleExpression") != config.model_quality_monitoring_cron_expression:
        return False
    job_definition_name = schedule_config.get("MonitoringJobDefinitionName")
    if job_definition_name:
        return job_definition_name == config.model_quality_job_definition_name
    definition = schedule_config.get("MonitoringJobDefinition", {})
    if not isinstance(definition, dict):
        return False
    baseline = definition.get("BaselineConfig", {})
    if not isinstance(baseline, dict):
        return False
    inputs = definition.get("MonitoringInputs", [])
    endpoint_name = ""
    if isinstance(inputs, list):
        for item in inputs:
            if isinstance(item, dict):
                endpoint_input = item.get("EndpointInput", {})
                if isinstance(endpoint_input, dict) and endpoint_input.get("EndpointName"):
                    endpoint_name = str(endpoint_input["EndpointName"])
                    break
    return (
        endpoint_name == config.endpoint_name
        and baseline.get("ConstraintsResource", {}).get("S3Uri") == config.model_quality_constraints_s3_uri
        and baseline.get("StatisticsResource", {}).get("S3Uri") == config.model_quality_statistics_s3_uri
    )


def _create_with_retries(
    clients,
    request: dict[str, object],
    *,
    label: str,
    max_attempts: int = 3,
    poll_seconds: int = 15,
) -> dict[str, object]:
    call = request["_call"]
    payload = {key: value for key, value in request.items() if key != "_call"}
    for attempt in range(1, max_attempts + 1):
        try:
            return call(**payload)
        except ClientError as exc:
            if _client_error_code(exc) not in RETRYABLE_CREATE_ERRORS or attempt == max_attempts:
                raise
            code = _client_error_code(exc) or "Unknown"
            print(f"{label} hit transient {code}. Waiting {poll_seconds}s before retry {attempt + 1}/{max_attempts}...")
            time.sleep(poll_seconds)
    raise RuntimeError(f"{label} did not complete.")


def _native_unavailable_payload(
    *,
    config,
    image_uri: str,
    processing_compute,
    capture_modes: list[str],
    error: ClientError,
    stage: str,
) -> dict[str, object]:
    payload = {
        "model_quality_schedule_name": config.model_quality_schedule_name,
        "configured_model_quality_schedule_name": config.model_quality_schedule_name,
        "actual_model_quality_schedule_name": "",
        "model_quality_job_definition_name": config.model_quality_job_definition_name,
        "endpoint_name": config.endpoint_name,
        "status": "native_model_quality_schedule_unavailable",
        "failed_stage": stage,
        "monitoring_type": "ModelQuality",
        "ground_truth_s3_uri": config.model_quality_ground_truth_s3_uri,
        "model_quality_constraints_s3_uri": config.model_quality_constraints_s3_uri,
        "model_quality_reports_s3_uri": config.model_quality_reports_s3_uri,
        "capture_modes": capture_modes,
        "cron": config.model_quality_monitoring_cron_expression,
        "image_uri": image_uri,
        "compute_selection": processing_compute.to_dict(),
        "service_error": _client_error_details(error),
        "note": "SageMaker returned a service-side error while creating the native Model Quality Monitor resources.",
        "debug_next_steps": [
            "Check CloudTrail for CreateMonitoringSchedule and CreateModelQualityJobDefinition using the recorded request_id.",
            "Verify the IAM role has SageMaker, S3, CloudWatch Logs, and ECR pull permissions.",
            "Retry after a few minutes; HTTP 500 InternalFailure is returned by the SageMaker control plane.",
        ],
    }
    write_metadata(config, "model_quality_schedule", payload)
    return payload


def create_model_quality_schedule() -> dict[str, object]:
    config = load_config(validate=True, require_execution_role=True)
    if not config.enable_model_monitor:
        payload = {"skipped": True, "reason": "ENABLE_MODEL_MONITOR=false"}
        write_metadata(config, "model_quality_schedule", payload)
        return payload
    if not config.capture_endpoint_output:
        raise RuntimeError(
            "Native SageMaker Model Quality Monitor requires CAPTURE_ENDPOINT_OUTPUT=true so endpoint predictions are captured."
        )
    validate_monitoring_schedule_expression(config.model_quality_monitoring_cron_expression)

    clients = create_clients(config)
    capture_modes = _endpoint_capture_modes(clients, config.endpoint_name)
    missing_modes = [mode for mode in ["Input", "Output"] if mode not in capture_modes]
    if missing_modes:
        raise RuntimeError(
            f"Endpoint Data Capture must include Input and Output for native Model Quality Monitor. "
            f"Missing: {', '.join(missing_modes)}. Run `python -m src.deploy_model --wait --force-recreate`."
        )

    processing_compute = select_instance_type(
        config,
        workload="processing",
        preferred=config.model_monitor_processing_instance_type,
        candidates=config.model_monitor_processing_instance_type_candidates_list,
        session=clients.session,
    )
    if processing_compute.source == "fallback-no-positive-quota":
        raise RuntimeError("No SageMaker processing quota is available for Model Quality Monitor jobs.")

    image_uri = model_monitor_image_uri(config)
    baseline_metadata = read_metadata(config, "model_quality_baseline")
    if not baseline_metadata:
        raise RuntimeError(
            "Model Quality Monitor requires a model-quality baseline constraints file. "
            "Run `python -m src.generate_model_quality_baseline --wait` before creating the schedule."
        )
    existing_schedule = _describe_schedule(clients, config.model_quality_schedule_name)
    if existing_schedule and _existing_schedule_matches(existing_schedule, config=config):
        payload = {
            "model_quality_schedule_name": config.model_quality_schedule_name,
            "configured_model_quality_schedule_name": config.model_quality_schedule_name,
            "actual_model_quality_schedule_name": config.model_quality_schedule_name,
            "model_quality_job_definition_name": config.model_quality_job_definition_name,
            "endpoint_name": config.endpoint_name,
            "status": "existing",
            "monitoring_type": "ModelQuality",
            "ground_truth_s3_uri": config.model_quality_ground_truth_s3_uri,
            "model_quality_constraints_s3_uri": config.model_quality_constraints_s3_uri,
            "model_quality_statistics_s3_uri": config.model_quality_statistics_s3_uri,
            "model_quality_reports_s3_uri": config.model_quality_reports_s3_uri,
            "capture_modes": capture_modes,
            "cron": config.model_quality_monitoring_cron_expression,
            "image_uri": image_uri,
            "compute_selection": processing_compute.to_dict(),
        }
        write_metadata(config, "model_quality_schedule", payload)
        return payload

    if existing_schedule:
        clients.sagemaker.delete_monitoring_schedule(MonitoringScheduleName=config.model_quality_schedule_name)
        _wait_for_schedule_deleted(clients, config.model_quality_schedule_name)

    actual_schedule_name = config.model_quality_schedule_name
    schedule_route = "inline_monitoring_job_definition"
    job_definition_response: dict[str, object] = {}
    try:
        schedule_response = _create_with_retries(
            clients,
            {
                "_call": clients.sagemaker.create_monitoring_schedule,
                **_inline_schedule_request(
                    config=config,
                    image_uri=image_uri,
                    instance_type=processing_compute.selected_instance_type,
                    baseline_metadata=baseline_metadata,
                    schedule_name=actual_schedule_name,
                ),
            },
            label="CreateMonitoringSchedule",
        )
    except ClientError as exc:
        if _client_error_code(exc) != "InternalFailure":
            raise
        actual_schedule_name = _fallback_schedule_name(config.model_quality_schedule_name)
        print(
            "CreateMonitoringSchedule returned InternalFailure for "
            f"{config.model_quality_schedule_name}. Trying fallback schedule name {actual_schedule_name}..."
        )
        try:
            schedule_response = _create_with_retries(
                clients,
                {
                    "_call": clients.sagemaker.create_monitoring_schedule,
                    **_inline_schedule_request(
                        config=config,
                        image_uri=image_uri,
                        instance_type=processing_compute.selected_instance_type,
                        baseline_metadata=baseline_metadata,
                        schedule_name=actual_schedule_name,
                    ),
                },
                label="CreateMonitoringSchedule",
            )
            schedule_route = "inline_monitoring_job_definition_fallback_name"
        except ClientError as fallback_error:
            if _client_error_code(fallback_error) != "InternalFailure":
                raise
            print(
                "Inline CreateMonitoringSchedule still returned InternalFailure. "
                "Trying explicit CreateModelQualityJobDefinition route..."
            )
            schedule_route = "model_quality_job_definition"
            try:
                _delete_job_definition_if_exists(clients, config.model_quality_job_definition_name)
                job_definition_response = _create_with_retries(
                    clients,
                    {
                        "_call": clients.sagemaker.create_model_quality_job_definition,
                        **_model_quality_job_definition_request(
                            config=config,
                            image_uri=image_uri,
                            instance_type=processing_compute.selected_instance_type,
                        ),
                    },
                    label="CreateModelQualityJobDefinition",
                )
                schedule_response = _create_with_retries(
                    clients,
                    {
                        "_call": clients.sagemaker.create_monitoring_schedule,
                        "MonitoringScheduleName": actual_schedule_name,
                        "MonitoringScheduleConfig": {
                            "ScheduleConfig": {"ScheduleExpression": config.model_quality_monitoring_cron_expression},
                            "MonitoringJobDefinitionName": config.model_quality_job_definition_name,
                            "MonitoringType": "ModelQuality",
                        },
                        "Tags": config.tags,
                    },
                    label="CreateMonitoringSchedule",
                )
            except ClientError as typed_error:
                if _client_error_code(typed_error) == "InternalFailure":
                    return _native_unavailable_payload(
                        config=config,
                        image_uri=image_uri,
                        processing_compute=processing_compute,
                        capture_modes=capture_modes,
                        error=typed_error,
                        stage="create_model_quality_schedule_all_routes",
                    )
                raise

    capture_metadata = read_metadata(config, "model_quality_capture")
    payload = {
        "model_quality_schedule_name": actual_schedule_name,
        "configured_model_quality_schedule_name": config.model_quality_schedule_name,
        "actual_model_quality_schedule_name": actual_schedule_name,
        "model_quality_job_definition_name": config.model_quality_job_definition_name,
        "endpoint_name": config.endpoint_name,
        "status": "created",
        "schedule_route": schedule_route,
        "monitoring_type": "ModelQuality",
        "problem_type": config.model_quality_problem_type,
        "ground_truth_s3_uri": config.model_quality_ground_truth_s3_uri,
        "model_quality_constraints_s3_uri": config.model_quality_constraints_s3_uri,
        "model_quality_statistics_s3_uri": config.model_quality_statistics_s3_uri,
        "model_quality_reports_s3_uri": config.model_quality_reports_s3_uri,
        "capture_modes": capture_modes,
        "inference_attribute": config.model_quality_inference_attribute,
        "probability_attribute": config.model_quality_probability_attribute,
        "attribute_note": (
            "Endpoint output already includes a discrete prediction field. "
            "ProbabilityThresholdAttribute is omitted for this JSON endpoint contract."
        ),
        "analysis_window": {
            "start_time_offset": config.model_quality_start_time_offset,
            "end_time_offset": config.model_quality_end_time_offset,
        },
        "cron": config.model_quality_monitoring_cron_expression,
        "image_uri": image_uri,
        "compute_selection": processing_compute.to_dict(),
        "job_definition_response": job_definition_response,
        "monitoring_schedule_response": schedule_response,
        "latest_ground_truth_written": capture_metadata.get("sagemaker_ground_truth_s3_uri", ""),
        "baseline_job_name": baseline_metadata.get("baseline_job_name", ""),
        "cost_warning": "Model Quality schedules create periodic processing jobs until deleted.",
    }
    write_metadata(config, "model_quality_schedule", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(create_model_quality_schedule(), indent=2, default=str))


if __name__ == "__main__":
    main()
