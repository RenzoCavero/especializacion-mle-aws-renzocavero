from __future__ import annotations

import argparse

from .aws_clients import client_error_code, clients
from .config import ConfigError, load_config, read_json, utc_now, write_json


def create_sagemaker_model() -> dict[str, object]:
    config = load_config(require_aws=True)
    model_resolution = read_json(config.metadata_path("model_resolution.json"))
    aws = clients(config)
    sagemaker = aws.sagemaker

    model_name = config.model_name
    try:
        existing = sagemaker.describe_model(ModelName=model_name)
        metadata = {
            "model_name": model_name,
            "model_arn": existing.get("ModelArn"),
            "status": "reused_existing",
            "created_by_lab": True,
            "model_artifact_s3_uri": model_resolution["model_artifact_s3_uri"],
            "image_uri": model_resolution["image_uri"],
            "updated_at": utc_now(),
        }
        write_json(config.metadata_path("sagemaker_model.json"), metadata)
        print(f"SageMaker Model existente reutilizado: {model_name}")
        return metadata
    except Exception as exc:
        if client_error_code(exc) not in {"ValidationException", "ResourceNotFound"}:
            raise

    container = {
        "Image": model_resolution["image_uri"],
        "ModelDataUrl": model_resolution["model_artifact_s3_uri"],
        "Environment": {
            "SAGEMAKER_PROGRAM": "inference.py",
            "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
            "SAGEMAKER_REGION": config.aws_region,
            "MODEL_VERSION": model_resolution.get("model_package_arn") or "standalone-v1",
        },
    }
    sagemaker.create_model(
        ModelName=model_name,
        ExecutionRoleArn=config.sagemaker_execution_role_arn,
        PrimaryContainer=container,
        Tags=config.tags,
    )
    description = sagemaker.describe_model(ModelName=model_name)
    metadata = {
        "model_name": model_name,
        "model_arn": description.get("ModelArn"),
        "status": "created",
        "created_by_lab": True,
        "model_artifact_s3_uri": model_resolution["model_artifact_s3_uri"],
        "image_uri": model_resolution["image_uri"],
        "created_at": utc_now(),
    }
    write_json(config.metadata_path("sagemaker_model.json"), metadata)
    print(f"SageMaker Model creado: {model_name}")
    return metadata


def main() -> None:
    argparse.ArgumentParser(description="Crear SageMaker Model.").parse_args()
    try:
        create_sagemaker_model()
    except ConfigError:
        raise
    except Exception as exc:
        if client_error_code(exc) in {"AccessDenied", "AccessDeniedException"}:
            raise SystemExit("Permisos insuficientes para crear SageMaker Model.") from exc
        raise


if __name__ == "__main__":
    main()
