"""Validate and document SageMaker Data Capture configuration."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, write_metadata


def describe_data_capture() -> dict[str, object]:
    config = load_config(validate=True)
    if not config.enable_data_capture:
        payload = {"enabled": False, "reason": "ENABLE_DATA_CAPTURE=false"}
        write_metadata(config, "data_capture", payload)
        return payload

    clients = create_clients(config)
    endpoint = clients.sagemaker.describe_endpoint(EndpointName=config.endpoint_name)
    endpoint_config = clients.sagemaker.describe_endpoint_config(EndpointConfigName=endpoint["EndpointConfigName"])
    capture = endpoint_config.get("DataCaptureConfig", {})
    endpoint_capture = endpoint.get("DataCaptureConfig", {})
    payload = {
        "enabled": bool(capture.get("EnableCapture")),
        "endpoint_name": config.endpoint_name,
        "endpoint_status": endpoint.get("EndpointStatus"),
        "endpoint_config_name": endpoint["EndpointConfigName"],
        "data_capture_s3_uri": capture.get("DestinationS3Uri", config.data_capture_s3_uri),
        "endpoint_capture_status": endpoint_capture.get("CaptureStatus", "NotReported"),
        "endpoint_capture_config": endpoint_capture,
        "capture_config": capture,
        "capture_modes": [item.get("CaptureMode") for item in capture.get("CaptureOptions", [])],
        "model_monitor_note": (
            "This lab captures endpoint Input and Output by default so the native SageMaker Model Quality "
            "Monitor can merge predictions with delayed ground truth. Data Quality monitoring still reads the "
            "endpoint input features; output capture requires the endpoint response to stay JSON-compatible."
        ),
        "model_monitor_input_prefix": config.data_capture_s3_uri,
        "console_note": (
            "In SageMaker Studio, Data Capture can appear under the endpoint Settings/Details instead of a "
            "separate Data Capture tab. The authoritative checks are Endpoint DataCaptureConfig and S3 objects."
        ),
    }
    write_metadata(config, "data_capture", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(describe_data_capture(), indent=2, default=str))


if __name__ == "__main__":
    main()
