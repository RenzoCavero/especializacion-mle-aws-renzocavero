from __future__ import annotations

import argparse

from .aws_clients import client_error_code, clients
from .config import load_config, read_json, utc_now, write_json


def _data_capture_config(config) -> dict[str, object] | None:
    if not config.enable_data_capture:
        return None
    capture = {
        "EnableCapture": True,
        "InitialSamplingPercentage": 100,
        "DestinationS3Uri": config.data_capture_s3_uri,
        "CaptureOptions": [{"CaptureMode": "Input"}, {"CaptureMode": "Output"}],
        "CaptureContentTypeHeader": {
            "JsonContentTypes": ["application/json"],
            "CsvContentTypes": ["text/csv"],
        },
    }
    if config.kms_key_id:
        capture["KmsKeyId"] = config.kms_key_id
    return capture


def create_endpoint_config() -> dict[str, object]:
    config = load_config(require_aws=True)
    model_metadata = read_json(config.metadata_path("sagemaker_model.json"))
    sagemaker = clients(config).sagemaker
    endpoint_config_name = config.endpoint_config_name

    try:
        existing = sagemaker.describe_endpoint_config(EndpointConfigName=endpoint_config_name)
        metadata = {
            "endpoint_config_name": endpoint_config_name,
            "endpoint_config_arn": existing.get("EndpointConfigArn"),
            "status": "reused_existing",
            "model_name": model_metadata["model_name"],
            "data_capture_s3_uri": config.data_capture_s3_uri if config.enable_data_capture else "",
            "updated_at": utc_now(),
        }
        write_json(config.metadata_path("endpoint_config.json"), metadata)
        print(f"Endpoint config existente reutilizado: {endpoint_config_name}")
        return metadata
    except Exception as exc:
        if client_error_code(exc) not in {"ValidationException", "ResourceNotFound"}:
            raise

    production_variant = {
        "VariantName": "AllTraffic",
        "ModelName": model_metadata["model_name"],
        "InitialInstanceCount": config.initial_instance_count,
        "InstanceType": config.instance_type,
        "InitialVariantWeight": 1.0,
    }
    request = {
        "EndpointConfigName": endpoint_config_name,
        "ProductionVariants": [production_variant],
        "Tags": config.tags,
    }
    capture = _data_capture_config(config)
    if capture:
        request["DataCaptureConfig"] = capture
    sagemaker.create_endpoint_config(**request)
    description = sagemaker.describe_endpoint_config(EndpointConfigName=endpoint_config_name)
    metadata = {
        "endpoint_config_name": endpoint_config_name,
        "endpoint_config_arn": description.get("EndpointConfigArn"),
        "status": "created",
        "model_name": model_metadata["model_name"],
        "instance_type": config.instance_type,
        "initial_instance_count": config.initial_instance_count,
        "production_variant": production_variant,
        "data_capture_enabled": config.enable_data_capture,
        "data_capture_s3_uri": config.data_capture_s3_uri if config.enable_data_capture else "",
        "created_at": utc_now(),
    }
    write_json(config.metadata_path("endpoint_config.json"), metadata)
    print(f"Endpoint config creado: {endpoint_config_name}")
    return metadata


def main() -> None:
    argparse.ArgumentParser(description="Crear SageMaker Endpoint Configuration.").parse_args()
    try:
        create_endpoint_config()
    except Exception as exc:
        if client_error_code(exc) in {"AccessDenied", "AccessDeniedException"}:
            raise SystemExit("Permisos insuficientes para crear endpoint config.") from exc
        raise


if __name__ == "__main__":
    main()
