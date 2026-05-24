"""Validate endpoint prerequisites for native Model Quality monitoring."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, write_metadata


def validate_model_quality_endpoint() -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    endpoint = clients.sagemaker.describe_endpoint(EndpointName=config.endpoint_name)
    endpoint_config = clients.sagemaker.describe_endpoint_config(EndpointConfigName=endpoint["EndpointConfigName"])
    capture = endpoint_config.get("DataCaptureConfig", {})
    capture_modes = sorted(
        str(item.get("CaptureMode"))
        for item in capture.get("CaptureOptions", [])
        if isinstance(item, dict) and item.get("CaptureMode")
    )
    missing_modes = [mode for mode in ["Input", "Output"] if mode not in capture_modes]
    status = str(endpoint.get("EndpointStatus", ""))

    issues: list[str] = []
    if status != "InService":
        issues.append(f"Endpoint must be InService; current status is {status}.")
    if not capture.get("EnableCapture"):
        issues.append("Data Capture must be enabled on the endpoint config.")
    if missing_modes:
        issues.append(f"Data Capture must include Input and Output. Missing: {', '.join(missing_modes)}.")
    if not config.capture_endpoint_output:
        issues.append("CAPTURE_ENDPOINT_OUTPUT must be true for native Model Quality monitoring.")

    payload = {
        "endpoint_name": config.endpoint_name,
        "endpoint_status": status,
        "endpoint_config_name": endpoint["EndpointConfigName"],
        "data_capture_enabled": bool(capture.get("EnableCapture")),
        "capture_modes": capture_modes,
        "capture_s3_uri": capture.get("DestinationS3Uri", ""),
        "response_contract": {
            "expected_content_type": "application/json",
            "expected_prediction_attribute": config.model_quality_inference_attribute,
            "expected_probability_attribute": config.model_quality_probability_attribute,
        },
        "inference_id_note": "InferenceId is not endpoint configuration; it is supplied per InvokeEndpoint request.",
        "status": "ready" if not issues else "not_ready",
        "issues": issues,
        "fix": (
            "Run `python -m src.deploy_model --wait` after setting CAPTURE_ENDPOINT_OUTPUT=true, "
            "or `python -m src.deploy_model --wait --force-recreate` if the endpoint config cannot be updated in place."
        ),
    }
    write_metadata(config, "model_quality_endpoint_validation", payload)
    if issues:
        joined = "\n- ".join(issues)
        raise RuntimeError(f"Endpoint is not ready for Model Quality monitoring:\n- {joined}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(validate_model_quality_endpoint(), indent=2, default=str))


if __name__ == "__main__":
    main()
