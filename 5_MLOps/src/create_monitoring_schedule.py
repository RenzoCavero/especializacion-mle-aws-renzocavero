"""Create a SageMaker Model Monitor schedule for the endpoint."""

from __future__ import annotations

import argparse
import json
import re
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


MODEL_MONITOR_IMAGE_ACCOUNTS = {
    "us-east-1": "156813124566",
    "us-east-2": "777275614652",
    "us-west-1": "707377530322",
    "us-west-2": "159807026194",
}
RETRYABLE_CREATE_SCHEDULE_ERRORS = {
    "ConflictException",
    "InternalFailure",
    "ResourceInUse",
    "ResourceInUseException",
    "ThrottlingException",
    "TooManyRequestsException",
}


def model_monitor_image_uri(config) -> str:
    if config.model_monitor_image_uri:
        return config.model_monitor_image_uri
    account = MODEL_MONITOR_IMAGE_ACCOUNTS.get(config.aws_region)
    if not account:
        raise ValueError(
            "No default SageMaker Model Monitor image is configured for this region. "
            "Set MODEL_MONITOR_IMAGE_URI in .env using the AWS ECR paths documentation."
        )
    return f"{account}.dkr.ecr.{config.aws_region}.amazonaws.com/sagemaker-model-monitor-analyzer"


def validate_monitoring_schedule_expression(expression: str) -> None:
    normalized = expression.strip()
    if normalized == "NOW":
        return
    match = re.fullmatch(r"cron\(0 ([0-9]{1,2}|\*|[0-9]{1,2}/[0-9]{1,2}) \? \* \* \*\)", normalized)
    if not match:
        raise ValueError(
            "Invalid MONITORING_CRON_EXPRESSION for SageMaker Model Monitor. "
            "Use NOW, cron(0 * ? * * *) for hourly, cron(0 HH ? * * *) for daily at hour HH UTC, "
            "or cron(0 HH/N ? * * *) for every N hours. Model Monitor does not support minute 45 "
            "or sub-hour intervals such as every 45 minutes."
        )
    hour_part = match.group(1)
    if hour_part == "*":
        return
    if "/" in hour_part:
        start_hour, interval = [int(item) for item in hour_part.split("/", 1)]
        if start_hour > 23 or not 1 <= interval <= 24:
            raise ValueError(
                "Invalid MONITORING_CRON_EXPRESSION. Start hour must be 0-23 and interval must be 1-24 hours."
            )
        return
    if int(hour_part) > 23:
        raise ValueError("Invalid MONITORING_CRON_EXPRESSION. Hour must be between 0 and 23 UTC.")


def _describe_schedule(clients, name: str) -> dict[str, object] | None:
    try:
        return clients.sagemaker.describe_monitoring_schedule(MonitoringScheduleName=name)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"ResourceNotFound", "ValidationException"}:
            return None
        raise


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


def _is_retryable_create_schedule_error(exc: ClientError) -> bool:
    code = _client_error_code(exc)
    message = _client_error_message(exc).lower()
    if code in RETRYABLE_CREATE_SCHEDULE_ERRORS:
        return True
    return code == "ValidationException" and any(
        fragment in message for fragment in ["already exists", "delet", "pending", "in progress"]
    )


def _wait_for_schedule_deleted(clients, name: str, poll_seconds: int = 15) -> None:
    while True:
        description = _describe_schedule(clients, name)
        if description is None:
            return
        status = description.get("MonitoringScheduleStatus", "Deleting")
        print(f"Monitoring schedule {name} is {status}. Waiting {poll_seconds}s...")
        time.sleep(poll_seconds)


def _endpoint_name_from_schedule(description: dict[str, object]) -> str:
    schedule_config = description.get("MonitoringScheduleConfig", {})
    if not isinstance(schedule_config, dict):
        return ""
    definition = schedule_config.get("MonitoringJobDefinition", {})
    if not isinstance(definition, dict):
        return ""
    inputs = definition.get("MonitoringInputs", [])
    if not isinstance(inputs, list):
        return ""
    for item in inputs:
        if not isinstance(item, dict):
            continue
        endpoint_input = item.get("EndpointInput", {})
        if isinstance(endpoint_input, dict) and endpoint_input.get("EndpointName"):
            return str(endpoint_input["EndpointName"])
    return ""


def _existing_schedule_matches(
    description: dict[str, object],
    *,
    config,
    image_uri: str,
    instance_type: str,
) -> bool:
    schedule_config = description.get("MonitoringScheduleConfig", {})
    if not isinstance(schedule_config, dict):
        return False
    schedule_expression = schedule_config.get("ScheduleConfig", {}).get("ScheduleExpression")
    job_definition_name = schedule_config.get("MonitoringJobDefinitionName")
    if job_definition_name:
        return (
            schedule_expression == config.monitoring_cron_expression
            and job_definition_name == _job_definition_name(config.monitoring_schedule_name)
        )
    definition = schedule_config.get("MonitoringJobDefinition", {})
    if not isinstance(definition, dict):
        return False
    baseline = definition.get("BaselineConfig", {})
    resources = definition.get("MonitoringResources", {}).get("ClusterConfig", {})
    output_config = definition.get("MonitoringOutputConfig", {}).get("MonitoringOutputs", [{}])
    output_s3_uri = ""
    if isinstance(output_config, list) and output_config:
        output_s3 = output_config[0].get("S3Output", {}) if isinstance(output_config[0], dict) else {}
        output_s3_uri = str(output_s3.get("S3Uri", ""))
    return (
        schedule_expression == config.monitoring_cron_expression
        and _endpoint_name_from_schedule(description) == config.endpoint_name
        and baseline.get("StatisticsResource", {}).get("S3Uri") == config.statistics_s3_uri
        and baseline.get("ConstraintsResource", {}).get("S3Uri") == config.constraints_s3_uri
        and definition.get("MonitoringAppSpecification", {}).get("ImageUri") == image_uri
        and resources.get("InstanceType") == instance_type
        and output_s3_uri == config.monitoring_s3_uri
    )


def _create_monitoring_schedule_with_retries(
    clients,
    request: dict[str, object],
    *,
    config,
    image_uri: str,
    instance_type: str,
    max_attempts: int = 3,
    poll_seconds: int = 15,
) -> dict[str, object]:
    name = str(request["MonitoringScheduleName"])
    for attempt in range(1, max_attempts + 1):
        try:
            return clients.sagemaker.create_monitoring_schedule(**request)
        except ClientError as exc:
            existing = _describe_schedule(clients, name)
            if existing and _existing_schedule_matches(
                existing,
                config=config,
                image_uri=image_uri,
                instance_type=instance_type,
            ):
                return {
                    "status": "created-or-found-after-retryable-error",
                    "retryable_error": _client_error_details(exc),
                    "describe_monitoring_schedule": existing,
                }
            if not _is_retryable_create_schedule_error(exc) or attempt == max_attempts:
                raise
            code = _client_error_code(exc) or "Unknown"
            status = existing.get("MonitoringScheduleStatus") if existing else "not visible yet"
            print(
                f"CreateMonitoringSchedule hit transient {code}; "
                f"schedule is {status}. Waiting {poll_seconds}s before retry {attempt + 1}/{max_attempts}..."
            )
            time.sleep(poll_seconds)
    raise RuntimeError(f"Could not create monitoring schedule {name}.")


def _fallback_schedule_name(base_name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = f"-{timestamp}"
    return f"{base_name[: 63 - len(suffix)].strip('-')}{suffix}"


def _job_definition_name(base_name: str) -> str:
    suffix = "-data-quality-job-def"
    return f"{base_name[: 63 - len(suffix)].strip('-')}{suffix}"


def _delete_data_quality_job_definition_if_exists(clients, name: str) -> None:
    try:
        clients.sagemaker.delete_data_quality_job_definition(JobDefinitionName=name)
    except ClientError as exc:
        code = _client_error_code(exc)
        if code not in {"ResourceNotFound", "ValidationException"}:
            raise


def _monitoring_definition(
    *,
    config,
    image_uri: str,
    instance_type: str,
) -> dict[str, object]:
    return {
        "BaselineConfig": {
            "StatisticsResource": {"S3Uri": config.statistics_s3_uri},
            "ConstraintsResource": {"S3Uri": config.constraints_s3_uri},
        },
        "MonitoringInputs": [
            {
                "EndpointInput": {
                    "EndpointName": config.endpoint_name,
                    "LocalPath": "/opt/ml/processing/input/endpoint",
                    "S3InputMode": "File",
                    "S3DataDistributionType": "FullyReplicated",
                }
            }
        ],
        "MonitoringOutputConfig": {
            "MonitoringOutputs": [
                {
                    "S3Output": {
                        "S3Uri": config.monitoring_s3_uri,
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


def _data_quality_job_definition_request(
    *,
    name: str,
    config,
    image_uri: str,
    instance_type: str,
) -> dict[str, object]:
    definition = _monitoring_definition(config=config, image_uri=image_uri, instance_type=instance_type)
    return {
        "JobDefinitionName": name,
        "DataQualityBaselineConfig": definition["BaselineConfig"],
        "DataQualityAppSpecification": definition["MonitoringAppSpecification"],
        "DataQualityJobInput": {"EndpointInput": definition["MonitoringInputs"][0]["EndpointInput"]},
        "DataQualityJobOutputConfig": definition["MonitoringOutputConfig"],
        "JobResources": definition["MonitoringResources"],
        "RoleArn": definition["RoleArn"],
        "StoppingCondition": definition["StoppingCondition"],
        "Tags": config.tags,
    }


def _create_data_quality_job_definition(
    clients,
    *,
    name: str,
    config,
    image_uri: str,
    instance_type: str,
) -> dict[str, object]:
    _delete_data_quality_job_definition_if_exists(clients, name)
    request = _data_quality_job_definition_request(
        name=name,
        config=config,
        image_uri=image_uri,
        instance_type=instance_type,
    )
    return clients.sagemaker.create_data_quality_job_definition(**request)


def _native_schedule_unavailable_payload(
    *,
    config,
    image_uri: str,
    processing_compute,
    replacement_actions: list[dict[str, str]],
    error: ClientError,
    attempted_schedule_name: str,
    data_quality_job_definition_name: str = "",
) -> dict[str, object]:
    payload = {
        "monitoring_schedule_name": attempted_schedule_name,
        "configured_monitoring_schedule_name": config.monitoring_schedule_name,
        "actual_monitoring_schedule_name": "",
        "data_quality_job_definition_name": data_quality_job_definition_name,
        "endpoint_name": config.endpoint_name,
        "status": "native_schedule_unavailable",
        "monitoring_s3_uri": config.monitoring_s3_uri,
        "statistics_s3_uri": config.statistics_s3_uri,
        "constraints_s3_uri": config.constraints_s3_uri,
        "cron": config.monitoring_cron_expression,
        "image_uri": image_uri,
        "compute_selection": processing_compute.to_dict(),
        "replacement_actions": replacement_actions,
        "service_error": _client_error_details(error),
        "fallback_note": (
            "SageMaker CreateMonitoringSchedule returned repeated InternalFailure before a schedule became visible. "
            "The lab will continue by publishing fallback monitoring evidence in src.check_monitoring_results."
        ),
        "cost_warning": "No periodic Model Monitor schedule was created; no schedule processing cost will accrue from this failed request.",
    }
    write_metadata(config, "monitoring_schedule", payload)
    return payload


def create_schedule() -> dict[str, object]:
    config = load_config(validate=True, require_execution_role=True)
    if not config.enable_model_monitor:
        payload = {"skipped": True, "reason": "ENABLE_MODEL_MONITOR=false"}
        write_metadata(config, "monitoring_schedule", payload)
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
        raise RuntimeError(
            "No SageMaker processing quota is available for monitoring schedule jobs. "
            "Run `python -m src.compute --workload processing --inventory --limit 0`."
        )

    image_uri = model_monitor_image_uri(config)
    existing_schedule = _describe_schedule(clients, config.monitoring_schedule_name)
    replacement_actions: list[dict[str, str]] = []
    stored = read_metadata(config, "monitoring_schedule")
    stored_schedule_name = str(stored.get("actual_monitoring_schedule_name") or "")
    if not existing_schedule and stored_schedule_name and stored_schedule_name != config.monitoring_schedule_name:
        stored_schedule = _describe_schedule(clients, stored_schedule_name)
        if stored_schedule and _existing_schedule_matches(
            stored_schedule,
            config=config,
            image_uri=image_uri,
            instance_type=processing_compute.selected_instance_type,
        ):
            payload = {
                "monitoring_schedule_name": stored_schedule_name,
                "configured_monitoring_schedule_name": config.monitoring_schedule_name,
                "actual_monitoring_schedule_name": stored_schedule_name,
                "endpoint_name": config.endpoint_name,
                "status": "existing-fallback-name",
                "monitoring_s3_uri": config.monitoring_s3_uri,
                "statistics_s3_uri": config.statistics_s3_uri,
                "constraints_s3_uri": config.constraints_s3_uri,
                "cron": config.monitoring_cron_expression,
                "image_uri": image_uri,
                "compute_selection": processing_compute.to_dict(),
                "note": "Using fallback schedule name remembered from a previous AWS InternalFailure on the configured name.",
            }
            write_metadata(config, "monitoring_schedule", payload)
            return payload

    if existing_schedule and _existing_schedule_matches(
        existing_schedule,
        config=config,
        image_uri=image_uri,
        instance_type=processing_compute.selected_instance_type,
    ):
        payload = {
            "monitoring_schedule_name": config.monitoring_schedule_name,
            "actual_monitoring_schedule_name": config.monitoring_schedule_name,
            "endpoint_name": config.endpoint_name,
            "status": "existing",
            "monitoring_s3_uri": config.monitoring_s3_uri,
            "statistics_s3_uri": config.statistics_s3_uri,
            "constraints_s3_uri": config.constraints_s3_uri,
            "cron": config.monitoring_cron_expression,
            "image_uri": image_uri,
            "compute_selection": processing_compute.to_dict(),
        }
        write_metadata(config, "monitoring_schedule", payload)
        return payload

    if existing_schedule:
        clients.sagemaker.delete_monitoring_schedule(MonitoringScheduleName=config.monitoring_schedule_name)
        _wait_for_schedule_deleted(clients, config.monitoring_schedule_name)
        replacement_actions.append(
            {
                "resource": config.monitoring_schedule_name,
                "operation": "delete_monitoring_schedule",
                "reason": "schedule_configuration_changed",
            }
        )

    definition = _monitoring_definition(
        config=config,
        image_uri=image_uri,
        instance_type=processing_compute.selected_instance_type,
    )
    request = {
        "MonitoringScheduleName": config.monitoring_schedule_name,
        "MonitoringScheduleConfig": {
            "ScheduleConfig": {"ScheduleExpression": config.monitoring_cron_expression},
            "MonitoringType": "DataQuality",
            "MonitoringJobDefinition": definition,
        },
        "Tags": config.tags,
    }
    actual_schedule_name = config.monitoring_schedule_name
    try:
        response = _create_monitoring_schedule_with_retries(
            clients,
            request,
            config=config,
            image_uri=image_uri,
            instance_type=processing_compute.selected_instance_type,
        )
    except ClientError as exc:
        if _client_error_code(exc) != "InternalFailure":
            raise
        job_definition_name = _job_definition_name(config.monitoring_schedule_name)
        try:
            job_definition_response = _create_data_quality_job_definition(
                clients,
                name=job_definition_name,
                config=config,
                image_uri=image_uri,
                instance_type=processing_compute.selected_instance_type,
            )
        except ClientError as job_definition_error:
            if _client_error_code(job_definition_error) == "InternalFailure":
                replacement_actions.append(
                    {
                        "resource": job_definition_name,
                        "operation": "create_data_quality_job_definition_failed",
                        "reason": "CreateDataQualityJobDefinition returned repeated InternalFailure.",
                    }
                )
                return _native_schedule_unavailable_payload(
                    config=config,
                    image_uri=image_uri,
                    processing_compute=processing_compute,
                    replacement_actions=replacement_actions,
                    error=job_definition_error,
                    attempted_schedule_name=config.monitoring_schedule_name,
                    data_quality_job_definition_name=job_definition_name,
                )
            raise
        request = {
            "MonitoringScheduleName": config.monitoring_schedule_name,
            "MonitoringScheduleConfig": {
                "ScheduleConfig": {"ScheduleExpression": config.monitoring_cron_expression},
                "MonitoringJobDefinitionName": job_definition_name,
                "MonitoringType": "DataQuality",
            },
            "Tags": config.tags,
        }
        replacement_actions.append(
            {
                "resource": job_definition_name,
                "operation": "create_data_quality_job_definition",
                "reason": "Inline CreateMonitoringSchedule returned repeated InternalFailure.",
            }
        )
        print(
            "CreateMonitoringSchedule kept returning InternalFailure for "
            f"{config.monitoring_schedule_name}. Trying schedule creation via DataQualityJobDefinition {job_definition_name}..."
        )
        try:
            response = _create_monitoring_schedule_with_retries(
                clients,
                request,
                config=config,
                image_uri=image_uri,
                instance_type=processing_compute.selected_instance_type,
            )
        except ClientError as job_def_schedule_error:
            if _client_error_code(job_def_schedule_error) != "InternalFailure":
                raise
            actual_schedule_name = _fallback_schedule_name(config.monitoring_schedule_name)
            request["MonitoringScheduleName"] = actual_schedule_name
            replacement_actions.append(
                {
                    "resource": actual_schedule_name,
                    "operation": "fallback_monitoring_schedule_name",
                    "reason": "CreateMonitoringSchedule returned repeated InternalFailure for the configured name.",
                }
            )
            print(
                "CreateMonitoringSchedule still returned InternalFailure through the job definition route. "
                f"Trying fallback schedule name {actual_schedule_name}..."
            )
            try:
                response = _create_monitoring_schedule_with_retries(
                    clients,
                    request,
                    config=config,
                    image_uri=image_uri,
                    instance_type=processing_compute.selected_instance_type,
                )
            except ClientError as fallback_error:
                if _client_error_code(fallback_error) == "InternalFailure":
                    return _native_schedule_unavailable_payload(
                        config=config,
                        image_uri=image_uri,
                        processing_compute=processing_compute,
                        replacement_actions=replacement_actions,
                        error=fallback_error,
                        attempted_schedule_name=actual_schedule_name,
                        data_quality_job_definition_name=job_definition_name,
                    )
                raise
        response = {
            "data_quality_job_definition_response": job_definition_response,
            "monitoring_schedule_response": response,
        }
    payload = {
        "monitoring_schedule_name": actual_schedule_name,
        "configured_monitoring_schedule_name": config.monitoring_schedule_name,
        "actual_monitoring_schedule_name": actual_schedule_name,
        "data_quality_job_definition_name": locals().get("job_definition_name", ""),
        "endpoint_name": config.endpoint_name,
        "monitoring_s3_uri": config.monitoring_s3_uri,
        "statistics_s3_uri": config.statistics_s3_uri,
        "constraints_s3_uri": config.constraints_s3_uri,
        "cron": config.monitoring_cron_expression,
        "image_uri": image_uri,
        "compute_selection": processing_compute.to_dict(),
        "replacement_actions": replacement_actions,
        "service_response": response,
        "cost_warning": "Monitoring schedules create periodic processing jobs until deleted.",
        "sdk_note": "Implemented with boto3 low-level APIs for compatibility with SageMaker Python SDK v3.",
    }
    write_metadata(config, "monitoring_schedule", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(create_schedule(), indent=2, default=str))


if __name__ == "__main__":
    main()
