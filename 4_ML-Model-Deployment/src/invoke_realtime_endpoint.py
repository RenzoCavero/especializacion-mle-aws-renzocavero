from __future__ import annotations

import argparse
import json
from typing import Any

from .aws_clients import client_error_code, clients
from .config import ConfigError, load_config, load_feature_contract, read_json, utc_now, write_json
from .get_online_features import get_online_features
from .validate_request_response import normalize_response, validate_inference_request


def _read_body(response: dict[str, Any]) -> str:
    body = response.get("Body")
    if hasattr(body, "read"):
        return body.read().decode("utf-8")
    return str(body or "")


def invoke_realtime_endpoint(record_id: str | None = None) -> dict[str, Any]:
    config = load_config(require_aws=True)
    model_resolution = read_json(config.metadata_path("model_resolution.json"), default={})
    payload = get_online_features(record_id=record_id)
    validate_inference_request(payload, load_feature_contract(config))
    runtime = clients(config).sagemaker_runtime

    request_id = payload.get("request_id") or f"invoke-{utc_now()}"
    try:
        response = runtime.invoke_endpoint(
            EndpointName=config.endpoint_name,
            ContentType="application/json",
            Accept="application/json",
            Body=json.dumps(payload),
        )
    except Exception as exc:
        code = client_error_code(exc)
        if code in {"ValidationError", "ModelError", "InternalFailure", "AccessDeniedException"}:
            raise ConfigError(
                f"No se pudo invocar el endpoint {config.endpoint_name}. "
                f"Codigo AWS: {code}. Revisa contrato, permisos y CloudWatch Logs."
            ) from exc
        raise

    body_text = _read_body(response)
    try:
        raw = json.loads(body_text)
    except json.JSONDecodeError:
        raw = body_text.splitlines()[0] if body_text else 0.0
    normalized = normalize_response(
        raw,
        model_version=model_resolution.get("model_package_arn") or "standalone-v1",
        request_id=request_id,
    )
    output = {
        **normalized,
        "endpoint_name": config.endpoint_name,
        "invoked_at": utc_now(),
    }
    write_json(config.metadata_path("realtime_invocation.json"), output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Invocar SageMaker Real-Time Endpoint.")
    parser.add_argument("--record-id", default="", help="Record ID para Online Store.")
    args = parser.parse_args()
    invoke_realtime_endpoint(record_id=args.record_id or None)


if __name__ == "__main__":
    main()
