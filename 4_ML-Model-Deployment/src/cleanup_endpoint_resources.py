from __future__ import annotations

import argparse
import time
from typing import Any

from .aws_clients import client_error_code, clients
from .config import load_config, read_json, utc_now, write_json


def _exists(call, **kwargs) -> bool:
    try:
        call(**kwargs)
        return True
    except Exception as exc:
        return client_error_code(exc) not in {"ValidationException", "ResourceNotFound"}


def cleanup_endpoint_resources(wait: bool = True) -> dict[str, Any]:
    config = load_config(require_aws=True)
    sagemaker = clients(config).sagemaker
    endpoint_meta = read_json(config.metadata_path("realtime_endpoint.json"), default={})
    endpoint_config_meta = read_json(config.metadata_path("endpoint_config.json"), default={})
    model_meta = read_json(config.metadata_path("sagemaker_model.json"), default={})

    endpoint_name = endpoint_meta.get("endpoint_name") or config.endpoint_name
    endpoint_config_name = endpoint_config_meta.get("endpoint_config_name") or config.endpoint_config_name
    model_name = model_meta.get("model_name") or config.model_name
    actions: list[str] = []

    if _exists(sagemaker.describe_endpoint, EndpointName=endpoint_name):
        try:
            sagemaker.delete_endpoint(EndpointName=endpoint_name)
            actions.append(f"delete_endpoint:{endpoint_name}")
            if wait:
                for _ in range(60):
                    if not _exists(sagemaker.describe_endpoint, EndpointName=endpoint_name):
                        break
                    time.sleep(10)
        except Exception as exc:
            if client_error_code(exc) not in {"ValidationException", "ResourceNotFound"}:
                raise

    if _exists(sagemaker.describe_endpoint_config, EndpointConfigName=endpoint_config_name):
        try:
            sagemaker.delete_endpoint_config(EndpointConfigName=endpoint_config_name)
            actions.append(f"delete_endpoint_config:{endpoint_config_name}")
        except Exception as exc:
            if client_error_code(exc) not in {"ValidationException", "ResourceNotFound"}:
                raise

    if model_meta.get("created_by_lab", True) and _exists(sagemaker.describe_model, ModelName=model_name):
        try:
            sagemaker.delete_model(ModelName=model_name)
            actions.append(f"delete_model:{model_name}")
        except Exception as exc:
            if client_error_code(exc) not in {"ValidationException", "ResourceNotFound"}:
                raise

    metadata = {
        "actions": actions,
        "preserved_external_resources": [
            "Model Package",
            "Model Package Group",
            "Feature Group",
            "Offline Store",
            "Online Store",
        ],
        "completed_at": utc_now(),
    }
    write_json(config.metadata_path("cleanup_endpoint.json"), metadata)
    print("Cleanup endpoint/model/config completado.")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Eliminar endpoint, endpoint config y model del laboratorio.")
    parser.add_argument("--no-wait", action="store_true", help="No esperar borrado del endpoint.")
    args = parser.parse_args()
    cleanup_endpoint_resources(wait=not args.no_wait)


if __name__ == "__main__":
    main()
