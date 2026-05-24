"""Deploy the latest approved model to a SageMaker real-time endpoint."""

from __future__ import annotations

import argparse
import json
import tarfile
import tempfile
import time
from pathlib import Path

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    class ClientError(Exception):
        response = {"Error": {"Code": "Unknown"}}

from .aws_clients import create_clients
from .compute import select_instance_type
from .config import load_config, read_metadata, write_metadata
from .resolve_approved_model import resolve_approved_model


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    bucket_key = uri[5:]
    bucket, _, key = bucket_key.partition("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI without bucket/key: {uri}")
    return bucket, key


def _exists(callable_obj, **kwargs) -> bool:
    try:
        callable_obj(**kwargs)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"ValidationException", "ResourceNotFound"}:
            return False
        raise


def _describe_or_none(callable_obj, **kwargs) -> dict[str, object] | None:
    try:
        return callable_obj(**kwargs)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"ValidationException", "ResourceNotFound"}:
            return None
        raise


def _wait_for_endpoint_deleted(clients, endpoint_name: str, poll_seconds: int = 15) -> None:
    while True:
        description = _describe_or_none(clients.sagemaker.describe_endpoint, EndpointName=endpoint_name)
        if description is None:
            return
        print(f"Endpoint {endpoint_name} is being deleted. Waiting {poll_seconds}s...")
        time.sleep(poll_seconds)


def _wait_for_monitoring_schedule_deleted(clients, schedule_name: str, poll_seconds: int = 15) -> None:
    while True:
        description = _describe_or_none(
            clients.sagemaker.describe_monitoring_schedule,
            MonitoringScheduleName=schedule_name,
        )
        if description is None:
            return
        status = description.get("MonitoringScheduleStatus", "Deleting")
        print(f"Monitoring schedule {schedule_name} is {status}. Waiting {poll_seconds}s...")
        time.sleep(poll_seconds)


def _monitoring_schedule_endpoint(description: dict[str, object]) -> str:
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


def _delete_monitoring_schedule_for_endpoint(clients, config, reason: str) -> list[dict[str, str]]:
    description = _describe_or_none(
        clients.sagemaker.describe_monitoring_schedule,
        MonitoringScheduleName=config.monitoring_schedule_name,
    )
    if description is None:
        return []

    schedule_endpoint = _monitoring_schedule_endpoint(description)
    if schedule_endpoint and schedule_endpoint != config.endpoint_name:
        return [
            {
                "resource": config.monitoring_schedule_name,
                "operation": "skip_delete_monitoring_schedule",
                "reason": f"schedule_targets_{schedule_endpoint}",
            }
        ]

    clients.sagemaker.delete_monitoring_schedule(MonitoringScheduleName=config.monitoring_schedule_name)
    _wait_for_monitoring_schedule_deleted(clients, config.monitoring_schedule_name)
    return [
        {
            "resource": config.monitoring_schedule_name,
            "operation": "delete_monitoring_schedule",
            "reason": reason,
        }
    ]


def _delete_monitoring_schedule_by_name(clients, name: str, reason: str) -> list[dict[str, str]]:
    if not name:
        return []
    description = _describe_or_none(
        clients.sagemaker.describe_monitoring_schedule,
        MonitoringScheduleName=name,
    )
    if description is None:
        return []
    clients.sagemaker.delete_monitoring_schedule(MonitoringScheduleName=name)
    _wait_for_monitoring_schedule_deleted(clients, name)
    return [{"resource": name, "operation": "delete_monitoring_schedule", "reason": reason}]


def _delete_model_quality_schedules(clients, config, reason: str) -> list[dict[str, str]]:
    actions = _delete_monitoring_schedule_by_name(clients, config.model_quality_schedule_name, reason)
    stored = read_metadata(config, "model_quality_schedule")
    actual_name = str(stored.get("actual_model_quality_schedule_name") or "")
    if actual_name and actual_name != config.model_quality_schedule_name:
        actions.extend(_delete_monitoring_schedule_by_name(clients, actual_name, reason))
    return actions


def _delete_if_exists(callable_obj, describe_obj, describe_kwargs: dict[str, str], delete_kwargs: dict[str, str]) -> bool:
    if _describe_or_none(describe_obj, **describe_kwargs) is None:
        return False
    callable_obj(**delete_kwargs)
    return True


def _replace_failed_lab_resources(clients, config, endpoint_description: dict[str, object] | None) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if endpoint_description is not None:
        status = str(endpoint_description.get("EndpointStatus", ""))
        if status != "Failed":
            return actions
        actions.extend(_delete_monitoring_schedule_for_endpoint(clients, config, "previous_endpoint_failed"))
        actions.extend(_delete_model_quality_schedules(clients, config, "previous_endpoint_failed"))
        clients.sagemaker.delete_endpoint(EndpointName=config.endpoint_name)
        actions.append({"resource": config.endpoint_name, "operation": "delete_endpoint", "reason": "previous_endpoint_failed"})
        _wait_for_endpoint_deleted(clients, config.endpoint_name)

    if endpoint_description is None and not config.is_standalone:
        return actions

    if _delete_if_exists(
        clients.sagemaker.delete_endpoint_config,
        clients.sagemaker.describe_endpoint_config,
        {"EndpointConfigName": config.endpoint_config_name},
        {"EndpointConfigName": config.endpoint_config_name},
    ):
        actions.append({"resource": config.endpoint_config_name, "operation": "delete_endpoint_config", "reason": "recreate_lab_deployment"})
    if _delete_if_exists(
        clients.sagemaker.delete_model,
        clients.sagemaker.describe_model,
        {"ModelName": config.sagemaker_model_name},
        {"ModelName": config.sagemaker_model_name},
    ):
        actions.append({"resource": config.sagemaker_model_name, "operation": "delete_model", "reason": "recreate_lab_deployment"})
    return actions


def _capture_options(config) -> list[dict[str, str]]:
    options = [{"CaptureMode": "Input"}]
    if config.capture_endpoint_output:
        options.append({"CaptureMode": "Output"})
    return options


def _build_capture_config(config) -> dict[str, object]:
    if not config.enable_data_capture:
        return {}
    return {
        "EnableCapture": True,
        "InitialSamplingPercentage": 100,
        "DestinationS3Uri": config.data_capture_s3_uri,
        "CaptureOptions": _capture_options(config),
        "CaptureContentTypeHeader": {
            "CsvContentTypes": ["text/csv"],
            "JsonContentTypes": ["application/json"],
        },
    }


def _capture_modes(capture_config: dict[str, object]) -> list[str]:
    options = capture_config.get("CaptureOptions", []) if capture_config else []
    return sorted(str(item.get("CaptureMode")) for item in options if isinstance(item, dict))


def _capture_config_differs(existing: dict[str, object] | None, desired: dict[str, object]) -> bool:
    existing_capture = (existing or {}).get("DataCaptureConfig", {})
    if not desired:
        return bool(existing_capture.get("EnableCapture"))
    return (
        not existing_capture.get("EnableCapture")
        or existing_capture.get("DestinationS3Uri") != desired.get("DestinationS3Uri")
        or _capture_modes(existing_capture) != _capture_modes(desired)
    )


def _replace_for_endpoint_config_change(
    clients,
    config,
    *,
    endpoint_description: dict[str, object] | None,
    reason: str,
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if endpoint_description is not None:
        actions.extend(_delete_monitoring_schedule_for_endpoint(clients, config, reason))
        actions.extend(_delete_model_quality_schedules(clients, config, reason))
        clients.sagemaker.delete_endpoint(EndpointName=config.endpoint_name)
        actions.append({"resource": config.endpoint_name, "operation": "delete_endpoint", "reason": reason})
        _wait_for_endpoint_deleted(clients, config.endpoint_name)
    actions.extend(_replace_failed_lab_resources(clients, config, None))
    return actions


def _model_resource_differs(
    model_description: dict[str, object] | None,
    *,
    model_package_arn: str,
    model_artifact_uri: str,
    image_uri: str,
) -> bool:
    if model_description is None:
        return False
    container = model_description.get("PrimaryContainer", {})
    if not isinstance(container, dict):
        return True
    existing_package = str(container.get("ModelPackageName") or "")
    if existing_package:
        return bool(model_package_arn) and existing_package != model_package_arn
    if model_artifact_uri and str(container.get("ModelDataUrl") or "") != model_artifact_uri:
        return True
    if image_uri and str(container.get("Image") or "") != image_uri:
        return True
    environment = container.get("Environment", {})
    if isinstance(environment, dict) and environment.get("SAGEMAKER_PROGRAM") != "inference.py":
        return True
    return False


def _upload_inference_source(s3_client, config) -> str:
    destination = f"{config.artifacts_s3_uri}/source/inference.tar.gz"
    bucket, key = _parse_s3_uri(destination)
    source_file = Path("training/inference.py")
    if not source_file.exists():
        raise FileNotFoundError("Missing training/inference.py for SageMaker endpoint deployment.")
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = Path(temp_dir) / "inference.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(source_file, arcname="inference.py")
        s3_client.upload_file(str(archive_path), bucket, key)
    return destination


def _inference_environment(config, source_s3_uri: str) -> dict[str, str]:
    return {
        "SAGEMAKER_PROGRAM": "inference.py",
        "SAGEMAKER_SUBMIT_DIRECTORY": source_s3_uri,
        "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
        "SAGEMAKER_REGION": config.aws_region,
    }


def deploy(wait: bool = False, poll_seconds: int = 30, force_recreate: bool = False) -> dict[str, object]:
    config = load_config(validate=True, require_execution_role=True)
    if not config.create_endpoint:
        payload = {"skipped": True, "reason": "CREATE_ENDPOINT=false"}
        write_metadata(config, "endpoint_deployment", payload)
        return payload

    clients = create_clients(config)
    desired_capture_config = _build_capture_config(config)
    endpoint_compute = select_instance_type(
        config,
        workload="endpoint",
        preferred=config.instance_type,
        candidates=config.endpoint_instance_type_candidates,
        session=clients.session,
    )
    if endpoint_compute.source == "fallback-no-positive-quota":
        raise RuntimeError(
            "No SageMaker endpoint quota is available for the configured candidates. "
            "Run `python -m src.compute --workload endpoint --inventory --limit 0`, "
            "update INSTANCE_TYPE_CANDIDATES with an instance that has quota, "
            "or request a SageMaker Service Quotas increase."
        )
    approved = resolve_approved_model()
    model_package_arn = str(approved.get("model_package_arn") or "")
    model_artifact_uri = str(approved.get("model_artifact_s3_uri") or "")
    image_uri = str(approved.get("image_uri") or config.model_image_uri or "")

    endpoint_description = _describe_or_none(clients.sagemaker.describe_endpoint, EndpointName=config.endpoint_name)
    endpoint_config_description = _describe_or_none(
        clients.sagemaker.describe_endpoint_config,
        EndpointConfigName=config.endpoint_config_name,
    )
    model_description = _describe_or_none(clients.sagemaker.describe_model, ModelName=config.sagemaker_model_name)
    replacement_actions: list[dict[str, str]]
    if force_recreate:
        replacement_actions = _delete_monitoring_schedule_for_endpoint(clients, config, "force_recreate")
        replacement_actions.extend(_delete_model_quality_schedules(clients, config, "force_recreate"))
        if endpoint_description is not None:
            clients.sagemaker.delete_endpoint(EndpointName=config.endpoint_name)
            replacement_actions.append({"resource": config.endpoint_name, "operation": "delete_endpoint", "reason": "force_recreate"})
            _wait_for_endpoint_deleted(clients, config.endpoint_name)
            endpoint_description = None
        replacement_actions.extend(_replace_failed_lab_resources(clients, config, None))
    elif (
        config.is_standalone
        and endpoint_config_description is not None
        and _capture_config_differs(endpoint_config_description, desired_capture_config)
    ):
        replacement_actions = _replace_for_endpoint_config_change(
            clients,
            config,
            endpoint_description=endpoint_description,
            reason="endpoint_config_capture_changed",
        )
        endpoint_description = None
        endpoint_config_description = None
        model_description = None
    elif config.is_standalone and _model_resource_differs(
        model_description,
        model_package_arn=model_package_arn,
        model_artifact_uri=model_artifact_uri,
        image_uri=image_uri,
    ):
        replacement_actions = _replace_for_endpoint_config_change(
            clients,
            config,
            endpoint_description=endpoint_description,
            reason="approved_model_changed",
        )
        endpoint_description = None
        endpoint_config_description = None
        model_description = None
    else:
        replacement_actions = _replace_failed_lab_resources(clients, config, endpoint_description)
        if replacement_actions:
            endpoint_description = None
            endpoint_config_description = None
            model_description = None

    inference_source_s3_uri = _upload_inference_source(clients.s3, config)
    container_environment = _inference_environment(config, inference_source_s3_uri)

    if not _exists(clients.sagemaker.describe_model, ModelName=config.sagemaker_model_name):
        if not model_artifact_uri or not image_uri:
            if model_package_arn:
                primary_container = {"ModelPackageName": model_package_arn}
            else:
                raise ValueError("MODEL_ARTIFACT_S3_URI deployment requires MODEL_IMAGE_URI when MODEL_PACKAGE_ARN is not used.")
        else:
            primary_container = {
                "Image": image_uri,
                "ModelDataUrl": model_artifact_uri,
                "Environment": container_environment,
            }
        clients.sagemaker.create_model(
            ModelName=config.sagemaker_model_name,
            ExecutionRoleArn=config.sagemaker_execution_role_arn,
            PrimaryContainer=primary_container,
            Tags=config.tags,
        )

    capture_config = desired_capture_config

    endpoint_config_kwargs = {
        "EndpointConfigName": config.endpoint_config_name,
        "ProductionVariants": [
            {
                "VariantName": "AllTraffic",
                "ModelName": config.sagemaker_model_name,
                "InitialInstanceCount": 1,
                "InstanceType": endpoint_compute.selected_instance_type,
                "InitialVariantWeight": 1.0,
            }
        ],
        "Tags": config.tags,
    }
    if capture_config:
        endpoint_config_kwargs["DataCaptureConfig"] = capture_config
    if config.kms_key_arn:
        endpoint_config_kwargs["KmsKeyId"] = config.kms_key_arn

    if not _exists(clients.sagemaker.describe_endpoint_config, EndpointConfigName=config.endpoint_config_name):
        clients.sagemaker.create_endpoint_config(**endpoint_config_kwargs)

    if _exists(clients.sagemaker.describe_endpoint, EndpointName=config.endpoint_name):
        action = "update_endpoint"
        clients.sagemaker.update_endpoint(
            EndpointName=config.endpoint_name,
            EndpointConfigName=config.endpoint_config_name,
        )
    else:
        action = "create_endpoint"
        clients.sagemaker.create_endpoint(
            EndpointName=config.endpoint_name,
            EndpointConfigName=config.endpoint_config_name,
            Tags=config.tags,
        )

    payload: dict[str, object] = {
        "action": action,
        "endpoint_name": config.endpoint_name,
        "endpoint_config_name": config.endpoint_config_name,
        "model_name": config.sagemaker_model_name,
        "model_package_arn": model_package_arn,
        "model_artifact_s3_uri": model_artifact_uri,
        "image_uri": image_uri,
        "inference_source_s3_uri": inference_source_s3_uri,
        "container_environment": container_environment,
        "replacement_actions": replacement_actions,
        "compute_selection": endpoint_compute.to_dict(),
        "data_capture_enabled": config.enable_data_capture,
        "capture_endpoint_output": config.capture_endpoint_output,
        "capture_modes": _capture_modes(capture_config),
        "data_capture_s3_uri": config.data_capture_s3_uri if config.enable_data_capture else "",
        "cost_warning": "SageMaker real-time endpoints generate cost while InService.",
    }

    if wait:
        while True:
            desc = clients.sagemaker.describe_endpoint(EndpointName=config.endpoint_name)
            status = desc.get("EndpointStatus")
            payload["endpoint_status"] = status
            if status in {"InService", "Failed"}:
                payload["endpoint_description"] = desc
                break
            print(f"Endpoint status: {status}. Waiting {poll_seconds}s...")
            time.sleep(poll_seconds)

    write_metadata(config, "endpoint_deployment", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--force-recreate", action="store_true")
    args = parser.parse_args()
    print(json.dumps(deploy(wait=args.wait, poll_seconds=args.poll_seconds, force_recreate=args.force_recreate), indent=2, default=str))


if __name__ == "__main__":
    main()
