from __future__ import annotations

import argparse

from .aws_clients import client_error_code, clients
from .config import ConfigError, load_config, read_json, utc_now, write_json


def _describe_endpoint(sagemaker, endpoint_name: str) -> dict[str, object] | None:
    try:
        return sagemaker.describe_endpoint(EndpointName=endpoint_name)
    except Exception as exc:
        if client_error_code(exc) in {"ValidationException", "ResourceNotFound"}:
            return None
        raise


def create_or_wait_endpoint(wait_only: bool = False, wait: bool | None = None) -> dict[str, object]:
    config = load_config(require_aws=True)
    endpoint_config = read_json(config.metadata_path("endpoint_config.json"))
    sagemaker = clients(config).sagemaker
    wait = config.wait_for_endpoint if wait is None else wait

    existing = _describe_endpoint(sagemaker, config.endpoint_name)
    if existing:
        status = existing.get("EndpointStatus")
        if status == "InService":
            metadata = {
                "endpoint_name": config.endpoint_name,
                "endpoint_arn": existing.get("EndpointArn"),
                "endpoint_status": status,
                "endpoint_config_name": existing.get("EndpointConfigName"),
                "status": "reused_existing",
                "updated_at": utc_now(),
            }
            write_json(config.metadata_path("realtime_endpoint.json"), metadata)
            print(f"Endpoint ya esta InService: {config.endpoint_name}")
            return metadata
        if status in {"Creating", "Updating", "SystemUpdating"} and wait:
            waiter = sagemaker.get_waiter("endpoint_in_service")
            waiter.wait(EndpointName=config.endpoint_name)
            existing = sagemaker.describe_endpoint(EndpointName=config.endpoint_name)
        elif status in {"Failed", "OutOfService"}:
            raise ConfigError(
                f"Endpoint {config.endpoint_name} esta en estado {status}. "
                "Revisa CloudWatch Logs antes de recrearlo."
            )
    elif wait_only:
        raise ConfigError(f"No existe el endpoint {config.endpoint_name} para esperar.")
    else:
        print(
            "ADVERTENCIA: un SageMaker Real-Time Endpoint genera costo mientras este activo. "
            "Ejecuta make destroy-endpoint o make destroy-all al terminar."
        )
        sagemaker.create_endpoint(
            EndpointName=config.endpoint_name,
            EndpointConfigName=endpoint_config["endpoint_config_name"],
            Tags=config.tags,
        )
        if wait:
            waiter = sagemaker.get_waiter("endpoint_in_service")
            waiter.wait(EndpointName=config.endpoint_name)
            existing = sagemaker.describe_endpoint(EndpointName=config.endpoint_name)
        else:
            existing = sagemaker.describe_endpoint(EndpointName=config.endpoint_name)

    metadata = {
        "endpoint_name": config.endpoint_name,
        "endpoint_arn": existing.get("EndpointArn") if existing else "",
        "endpoint_status": existing.get("EndpointStatus") if existing else "Creating",
        "endpoint_config_name": endpoint_config["endpoint_config_name"],
        "data_capture_s3_uri": endpoint_config.get("data_capture_s3_uri", ""),
        "created_or_checked_at": utc_now(),
    }
    write_json(config.metadata_path("realtime_endpoint.json"), metadata)
    print(f"Endpoint {config.endpoint_name}: {metadata['endpoint_status']}")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear o esperar SageMaker Real-Time Endpoint.")
    parser.add_argument("--wait-only", action="store_true", help="Solo esperar endpoint existente.")
    parser.add_argument("--no-wait", action="store_true", help="No esperar estado InService.")
    args = parser.parse_args()
    try:
        create_or_wait_endpoint(wait_only=args.wait_only, wait=not args.no_wait)
    except Exception as exc:
        if client_error_code(exc) in {"AccessDenied", "AccessDeniedException"}:
            raise SystemExit("Permisos insuficientes para crear o esperar endpoint.") from exc
        raise


if __name__ == "__main__":
    main()
