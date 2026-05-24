"""Delete endpoint resources created by the lab."""

from __future__ import annotations

import argparse
import json

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    class ClientError(Exception):
        response = {"Error": {"Code": "Unknown"}}

from .aws_clients import create_clients
from .config import load_config, write_metadata


def _try_delete(label: str, func, **kwargs) -> dict[str, str]:
    try:
        func(**kwargs)
        return {"resource": label, "status": "deleted"}
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"ValidationException", "ResourceNotFound"}:
            return {"resource": label, "status": "not_found"}
        return {"resource": label, "status": "error", "error": str(exc)}


def cleanup_endpoint(include_external: bool = False) -> dict[str, object]:
    config = load_config(validate=True)
    if config.is_integrated and not include_external:
        payload = {"skipped": True, "reason": "integrated_mode protects external endpoints by default"}
        write_metadata(config, "cleanup_endpoint", payload)
        return payload

    clients = create_clients(config)
    actions = [
        _try_delete(config.endpoint_name, clients.sagemaker.delete_endpoint, EndpointName=config.endpoint_name),
        _try_delete(config.endpoint_config_name, clients.sagemaker.delete_endpoint_config, EndpointConfigName=config.endpoint_config_name),
        _try_delete(config.sagemaker_model_name, clients.sagemaker.delete_model, ModelName=config.sagemaker_model_name),
        _try_delete(config.sagemaker_batch_model_name, clients.sagemaker.delete_model, ModelName=config.sagemaker_batch_model_name),
    ]
    payload = {"actions": actions, "include_external": include_external}
    write_metadata(config, "cleanup_endpoint", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-external", action="store_true")
    args = parser.parse_args()
    print(json.dumps(cleanup_endpoint(include_external=args.include_external), indent=2))


if __name__ == "__main__":
    main()
