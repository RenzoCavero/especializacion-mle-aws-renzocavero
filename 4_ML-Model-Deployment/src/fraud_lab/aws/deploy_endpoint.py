from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from src.aws_clients import client_error_code
from src.config import ConfigError, read_json, utc_now, write_json

from fraud_lab.aws.clients import FraudAwsClients
from fraud_lab.aws.config import FraudAwsConfig, load_fraud_aws_config
from fraud_lab.aws.model_registry import (
    ARTIFACT_PACKAGING_VERSION,
    SAGEMAKER_ENTRY_POINT,
    register_fraud_model_package,
)
from fraud_lab.features.feature_contract import FEATURE_VERSION, MODEL_VERSION

IN_PROGRESS_ENDPOINT_STATUSES = {"Creating", "Updating", "SystemUpdating", "RollingBack"}


def _metadata_path(config: FraudAwsConfig, file_name: str) -> Path:
    return config.lab_config.metadata_path(file_name)


def _load_or_register_model_package(config: FraudAwsConfig) -> dict[str, Any]:
    metadata_file = _metadata_path(config, "fraud_model_registry.json")
    if metadata_file.exists():
        metadata = read_json(metadata_file)
        if metadata.get("artifact_packaging_version") == ARTIFACT_PACKAGING_VERSION:
            return metadata
        print(
            "El artefacto registrado fue creado con un empaquetado anterior. "
            "Se registrara una nueva version del modelo de fraude."
        )
        return register_fraud_model_package()
    if config.fraud_model_package_arn and config.fraud_model_artifact_s3_uri:
        return {
            "model_package_group_name": config.fraud_model_package_group_name,
            "model_package_arn": config.fraud_model_package_arn,
            "model_artifact_s3_uri": config.fraud_model_artifact_s3_uri,
            "source_dir_s3_uri": "",
            "image_uri": "",
            "approval_status": "external",
        }
    return register_fraud_model_package()


def create_fraud_sagemaker_model(
    config: FraudAwsConfig | None = None,
    clients: FraudAwsClients | None = None,
) -> dict[str, Any]:
    config = config or load_fraud_aws_config()
    clients = clients or FraudAwsClients(config)
    sagemaker = clients.sagemaker
    model_package = _load_or_register_model_package(config)

    try:
        existing = sagemaker.describe_model(ModelName=config.fraud_model_name)
        existing_model_data = (
            existing.get("PrimaryContainer", {}).get("ModelDataUrl", "")
        )
        requested_model_data = model_package.get("model_artifact_s3_uri", "")
        if requested_model_data and existing_model_data != requested_model_data:
            print(
                "SageMaker Model fraud existente apunta a un artefacto anterior. "
                "Se eliminara y recreara."
            )
            sagemaker.delete_model(ModelName=config.fraud_model_name)
            raise RuntimeError("RECREATE_FRAUD_MODEL")
        metadata = {
            "model_name": config.fraud_model_name,
            "model_arn": existing.get("ModelArn"),
            "model_package_arn": model_package.get("model_package_arn", ""),
            "status": "reused_existing",
            "updated_at": utc_now(),
        }
        write_json(_metadata_path(config, "fraud_sagemaker_model.json"), metadata)
        print(f"SageMaker Model fraud existente reutilizado: {config.fraud_model_name}")
        return metadata
    except Exception as exc:
        if str(exc) == "RECREATE_FRAUD_MODEL":
            pass
        elif client_error_code(exc) not in {"ValidationException", "ResourceNotFound"}:
            raise

    image_uri = model_package.get("image_uri")
    model_data = model_package.get("model_artifact_s3_uri")
    source_dir = str(model_package.get("source_dir_s3_uri", ""))
    if not image_uri or not model_data:
        raise ConfigError(
            "No se pudo crear el SageMaker Model de fraude porque faltan "
            "image_uri o model_artifact_s3_uri. Ejecuta fraud-step 04 primero."
        )

    environment = {
        "SAGEMAKER_PROGRAM": SAGEMAKER_ENTRY_POINT,
        "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
        "SAGEMAKER_REGION": config.aws_region,
        "MODEL_VERSION": MODEL_VERSION,
        "FEATURE_VERSION": FEATURE_VERSION,
    }
    if source_dir:
        environment["SAGEMAKER_SUBMIT_DIRECTORY"] = source_dir

    sagemaker.create_model(
        ModelName=config.fraud_model_name,
        ExecutionRoleArn=config.sagemaker_execution_role_arn,
        PrimaryContainer={
            "Image": image_uri,
            "ModelDataUrl": model_data,
            "Environment": environment,
        },
        Tags=config.tags,
    )
    description = sagemaker.describe_model(ModelName=config.fraud_model_name)
    metadata = {
        "model_name": config.fraud_model_name,
        "model_arn": description.get("ModelArn"),
        "model_package_arn": model_package.get("model_package_arn", ""),
        "model_artifact_s3_uri": model_data,
        "source_dir_s3_uri": source_dir,
        "image_uri": image_uri,
        "status": "created",
        "created_at": utc_now(),
    }
    write_json(_metadata_path(config, "fraud_sagemaker_model.json"), metadata)
    print(f"SageMaker Model fraud creado: {config.fraud_model_name}")
    return metadata


def _data_capture_config(config: FraudAwsConfig) -> dict[str, Any] | None:
    if not config.fraud_enable_data_capture:
        return None
    return {
        "EnableCapture": True,
        "InitialSamplingPercentage": 100,
        "DestinationS3Uri": config.s3_uri("data-capture", config.fraud_endpoint_name),
        "CaptureOptions": [{"CaptureMode": "Input"}, {"CaptureMode": "Output"}],
        "CaptureContentTypeHeader": {
            "JsonContentTypes": ["application/json"],
            "CsvContentTypes": ["text/csv"],
        },
    }


def create_fraud_endpoint_config(
    config: FraudAwsConfig | None = None,
    clients: FraudAwsClients | None = None,
) -> dict[str, Any]:
    config = config or load_fraud_aws_config()
    clients = clients or FraudAwsClients(config)
    sagemaker = clients.sagemaker
    model_metadata = create_fraud_sagemaker_model(config, clients)

    try:
        existing = sagemaker.describe_endpoint_config(
            EndpointConfigName=config.fraud_endpoint_config_name
        )
        metadata = {
            "endpoint_config_name": config.fraud_endpoint_config_name,
            "endpoint_config_arn": existing.get("EndpointConfigArn"),
            "model_name": model_metadata["model_name"],
            "status": "reused_existing",
            "updated_at": utc_now(),
        }
        write_json(_metadata_path(config, "fraud_endpoint_config.json"), metadata)
        print(f"Endpoint config fraud existente reutilizado: {config.fraud_endpoint_config_name}")
        return metadata
    except Exception as exc:
        if client_error_code(exc) not in {"ValidationException", "ResourceNotFound"}:
            raise

    production_variant = {
        "VariantName": "AllTraffic",
        "ModelName": model_metadata["model_name"],
        "InitialInstanceCount": config.fraud_initial_instance_count,
        "InstanceType": config.fraud_instance_type,
        "InitialVariantWeight": 1.0,
    }
    request: dict[str, Any] = {
        "EndpointConfigName": config.fraud_endpoint_config_name,
        "ProductionVariants": [production_variant],
        "Tags": config.tags,
    }
    capture = _data_capture_config(config)
    if capture:
        request["DataCaptureConfig"] = capture
    sagemaker.create_endpoint_config(**request)
    description = sagemaker.describe_endpoint_config(
        EndpointConfigName=config.fraud_endpoint_config_name
    )
    metadata = {
        "endpoint_config_name": config.fraud_endpoint_config_name,
        "endpoint_config_arn": description.get("EndpointConfigArn"),
        "model_name": model_metadata["model_name"],
        "production_variant": production_variant,
        "data_capture_enabled": config.fraud_enable_data_capture,
        "data_capture_s3_uri": config.s3_uri("data-capture", config.fraud_endpoint_name)
        if config.fraud_enable_data_capture
        else "",
        "status": "created",
        "created_at": utc_now(),
    }
    write_json(_metadata_path(config, "fraud_endpoint_config.json"), metadata)
    print(f"Endpoint config fraud creado: {config.fraud_endpoint_config_name}")
    return metadata


def _describe_endpoint(sagemaker: Any, endpoint_name: str) -> dict[str, Any] | None:
    try:
        return sagemaker.describe_endpoint(EndpointName=endpoint_name)
    except Exception as exc:
        if client_error_code(exc) in {"ValidationException", "ResourceNotFound"}:
            return None
        raise


def _wait_endpoint_in_service_or_terminal(
    sagemaker: Any,
    endpoint_name: str,
    timeout_seconds: int = 1800,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_status = ""
    while time.time() < deadline:
        description = _describe_endpoint(sagemaker, endpoint_name)
        if not description:
            raise ConfigError(f"Endpoint {endpoint_name} no existe.")
        status = str(description.get("EndpointStatus", ""))
        if status != last_status:
            print(f"Endpoint {endpoint_name}: {status}")
            last_status = status
        if status in {"InService", "Failed", "OutOfService"}:
            return description
        time.sleep(30)
    raise TimeoutError(f"Timeout esperando endpoint {endpoint_name}.")


def create_fraud_realtime_endpoint(
    wait: bool = True,
    config: FraudAwsConfig | None = None,
    clients: FraudAwsClients | None = None,
) -> dict[str, Any]:
    config = config or load_fraud_aws_config()
    clients = clients or FraudAwsClients(config)
    sagemaker = clients.sagemaker

    existing = _describe_endpoint(sagemaker, config.fraud_endpoint_name)
    if existing:
        status = existing.get("EndpointStatus")
        if status in {"Creating", "Updating", "SystemUpdating"} and wait:
            existing = _wait_endpoint_in_service_or_terminal(
                sagemaker,
                config.fraud_endpoint_name,
            )
        elif status in {"Failed", "OutOfService"}:
            pass

        status = existing.get("EndpointStatus")
        if status in {"Failed", "OutOfService"}:
            print(
                f"Endpoint fraud {config.fraud_endpoint_name} esta en {status}. "
                "Se eliminara y recreara."
            )
            sagemaker.delete_endpoint(EndpointName=config.fraud_endpoint_name)
            if wait:
                _wait_endpoint_deleted(sagemaker, config.fraud_endpoint_name)
        else:
            metadata = {
                "endpoint_name": config.fraud_endpoint_name,
                "endpoint_arn": existing.get("EndpointArn"),
                "endpoint_status": existing.get("EndpointStatus"),
                "endpoint_config_name": existing.get("EndpointConfigName"),
                "status": "reused_existing",
                "updated_at": utc_now(),
            }
            write_json(_metadata_path(config, "fraud_realtime_endpoint.json"), metadata)
            print(f"Endpoint fraud existente: {config.fraud_endpoint_name} ({metadata['endpoint_status']})")
            return metadata

    endpoint_config = create_fraud_endpoint_config(config, clients)

    print(
        "ADVERTENCIA: el SageMaker Real-Time Endpoint de fraude genera costo mientras "
        "este activo. Ejecuta python -m src.lab_runner fraud-cleanup al terminar."
    )
    sagemaker.create_endpoint(
        EndpointName=config.fraud_endpoint_name,
        EndpointConfigName=endpoint_config["endpoint_config_name"],
        Tags=config.tags,
    )
    if wait:
        description = _wait_endpoint_in_service_or_terminal(
            sagemaker,
            config.fraud_endpoint_name,
        )
    else:
        description = sagemaker.describe_endpoint(EndpointName=config.fraud_endpoint_name)
    if str(description.get("EndpointStatus", "")) in {"Failed", "OutOfService"}:
        failure_reason = description.get("FailureReason", "sin FailureReason disponible")
        raise ConfigError(
            f"Endpoint {config.fraud_endpoint_name} termino en "
            f"{description.get('EndpointStatus')}. FailureReason: {failure_reason}"
        )
    metadata = {
        "endpoint_name": config.fraud_endpoint_name,
        "endpoint_arn": description.get("EndpointArn"),
        "endpoint_status": description.get("EndpointStatus"),
        "endpoint_config_name": endpoint_config["endpoint_config_name"],
        "data_capture_s3_uri": endpoint_config.get("data_capture_s3_uri", ""),
        "status": "created",
        "created_at": utc_now(),
    }
    write_json(_metadata_path(config, "fraud_realtime_endpoint.json"), metadata)
    print(f"Endpoint fraud {config.fraud_endpoint_name}: {metadata['endpoint_status']}")
    return metadata


def deploy_fraud_endpoint(wait: bool = True) -> dict[str, Any]:
    return create_fraud_realtime_endpoint(wait=wait)


def _wait_endpoint_deleted(sagemaker: Any, endpoint_name: str, timeout_seconds: int = 900) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not _describe_endpoint(sagemaker, endpoint_name):
            return
        time.sleep(15)
    raise TimeoutError(f"Timeout esperando eliminacion de endpoint {endpoint_name}.")


def _wait_endpoint_ready_for_delete(
    sagemaker: Any,
    endpoint_name: str,
    timeout_seconds: int = 1800,
) -> dict[str, Any] | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        description = _describe_endpoint(sagemaker, endpoint_name)
        if not description:
            return None
        status = str(description.get("EndpointStatus", ""))
        if status not in IN_PROGRESS_ENDPOINT_STATUSES:
            return description
        print(
            f"Endpoint {endpoint_name} esta en {status}; esperando a que termine "
            "la operacion en progreso para poder eliminarlo."
        )
        time.sleep(30)
    raise TimeoutError(
        f"Timeout esperando que el endpoint {endpoint_name} salga de estado in-progress."
    )


def cleanup_fraud_endpoint_resources(
    wait: bool = True,
    in_progress_timeout_seconds: int = 1800,
) -> dict[str, list[str]]:
    config = load_fraud_aws_config(require_operational=False)
    clients = FraudAwsClients(config)
    sagemaker = clients.sagemaker
    deleted: list[str] = []
    skipped: list[str] = []
    in_progress: list[str] = []

    endpoint_description = _describe_endpoint(sagemaker, config.fraud_endpoint_name)
    if endpoint_description:
        endpoint_deleted = False
        status = str(endpoint_description.get("EndpointStatus", ""))
        if status in IN_PROGRESS_ENDPOINT_STATUSES:
            if not wait:
                print(
                    f"Endpoint {config.fraud_endpoint_name} esta en {status}. "
                    "AWS no permite forzar DeleteEndpoint durante una operacion "
                    "en progreso; vuelve a ejecutar cleanup cuando pase a Failed, "
                    "InService u OutOfService."
                )
                in_progress.append(config.fraud_endpoint_name)
                skipped.extend(
                    [
                        config.fraud_endpoint_name,
                        config.fraud_endpoint_config_name,
                        config.fraud_model_name,
                    ]
                )
                return {
                    "deleted": deleted,
                    "skipped": skipped,
                    "in_progress": in_progress,
                }
            endpoint_description = _wait_endpoint_ready_for_delete(
                sagemaker,
                config.fraud_endpoint_name,
                timeout_seconds=in_progress_timeout_seconds,
            )
        if endpoint_description:
            try:
                sagemaker.delete_endpoint(EndpointName=config.fraud_endpoint_name)
                endpoint_deleted = True
            except Exception as exc:
                message = getattr(exc, "response", {}).get("Error", {}).get("Message", "")
                if "in-progress endpoint" in message:
                    if not wait:
                        in_progress.append(config.fraud_endpoint_name)
                        skipped.append(config.fraud_endpoint_name)
                        return {
                            "deleted": deleted,
                            "skipped": skipped,
                            "in_progress": in_progress,
                        }
                    _wait_endpoint_ready_for_delete(
                        sagemaker,
                        config.fraud_endpoint_name,
                        timeout_seconds=in_progress_timeout_seconds,
                    )
                    sagemaker.delete_endpoint(EndpointName=config.fraud_endpoint_name)
                    endpoint_deleted = True
                elif client_error_code(exc) in {"ValidationException", "ResourceNotFound"}:
                    skipped.append(config.fraud_endpoint_name)
                else:
                    raise
        if endpoint_deleted:
            deleted.append(config.fraud_endpoint_name)
        elif config.fraud_endpoint_name not in skipped:
            skipped.append(config.fraud_endpoint_name)
        if wait and endpoint_deleted:
            _wait_endpoint_deleted(sagemaker, config.fraud_endpoint_name)
    else:
        skipped.append(config.fraud_endpoint_name)

    try:
        sagemaker.delete_endpoint_config(
            EndpointConfigName=config.fraud_endpoint_config_name
        )
        deleted.append(config.fraud_endpoint_config_name)
    except Exception as exc:
        if client_error_code(exc) in {"ValidationException", "ResourceNotFound"}:
            skipped.append(config.fraud_endpoint_config_name)
        else:
            raise

    try:
        sagemaker.delete_model(ModelName=config.fraud_model_name)
        deleted.append(config.fraud_model_name)
    except Exception as exc:
        if client_error_code(exc) in {"ValidationException", "ResourceNotFound"}:
            skipped.append(config.fraud_model_name)
        else:
            raise

    return {"deleted": deleted, "skipped": skipped, "in_progress": in_progress}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create SageMaker Model, EndpointConfig and Real-Time Endpoint for fraud."
    )
    parser.add_argument("--no-wait", action="store_true", help="Do not wait for InService.")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete only fraud endpoint, endpoint config and SageMaker model.",
    )
    parser.add_argument(
        "--cleanup-timeout-seconds",
        type=int,
        default=1800,
        help="Max seconds to wait for an in-progress endpoint before cleanup.",
    )
    args = parser.parse_args()
    if args.cleanup:
        print(
            json.dumps(
                cleanup_fraud_endpoint_resources(
                    wait=not args.no_wait,
                    in_progress_timeout_seconds=args.cleanup_timeout_seconds,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return
    metadata = deploy_fraud_endpoint(wait=not args.no_wait)
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
