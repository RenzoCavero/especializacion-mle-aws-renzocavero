"""Check SageMaker Data Capture status and captured S3 objects."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

from .aws_clients import create_clients
from .config import load_config, write_metadata


def parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    bucket_key = uri[5:]
    bucket, _, key = bucket_key.partition("/")
    if not bucket:
        raise ValueError(f"Invalid S3 URI without bucket: {uri}")
    return bucket, key.strip("/")


def list_capture_objects(s3_client: Any, capture_s3_uri: str, limit: int = 10) -> dict[str, object]:
    bucket, prefix = parse_s3_uri(capture_s3_uri)
    paginator = s3_client.get_paginator("list_objects_v2")
    sample_objects: list[dict[str, object]] = []
    total = 0
    latest_modified = None
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            total += 1
            latest_modified = item.get("LastModified")
            if len(sample_objects) < limit:
                sample_objects.append(
                    {
                        "key": item.get("Key"),
                        "size": item.get("Size"),
                        "last_modified": item.get("LastModified"),
                    }
                )
    return {
        "bucket": bucket,
        "prefix": prefix,
        "object_count": total,
        "latest_modified": latest_modified,
        "sample_objects": sample_objects,
    }


def check_data_capture(wait: bool = False, timeout_seconds: int = 300, poll_seconds: int = 30) -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    deadline = time.time() + timeout_seconds

    while True:
        endpoint = clients.sagemaker.describe_endpoint(EndpointName=config.endpoint_name)
        endpoint_config_name = endpoint["EndpointConfigName"]
        endpoint_config = clients.sagemaker.describe_endpoint_config(EndpointConfigName=endpoint_config_name)
        capture_config = endpoint_config.get("DataCaptureConfig", {})
        capture_s3_uri = capture_config.get("DestinationS3Uri") or config.data_capture_s3_uri
        s3_listing = list_capture_objects(clients.s3, capture_s3_uri)
        found = int(s3_listing["object_count"]) > 0

        payload = {
            "endpoint_name": config.endpoint_name,
            "endpoint_status": endpoint.get("EndpointStatus"),
            "endpoint_config_name": endpoint_config_name,
            "endpoint_capture_status": endpoint.get("DataCaptureConfig", {}).get("CaptureStatus", "NotReported"),
            "enabled": bool(capture_config.get("EnableCapture")),
            "capture_s3_uri": capture_s3_uri,
            "s3_listing": s3_listing,
            "status": "capture_files_found" if found else "waiting_for_capture_files",
            "note": (
                "Data Capture writes asynchronously. Studio may not show a separate Data Capture tab; "
                "validate Endpoint DataCaptureConfig and captured .jsonl files in S3."
            ),
        }
        write_metadata(config, "data_capture_check", payload)

        if found or not wait or time.time() >= deadline:
            if wait and not found:
                payload["status"] = "capture_files_not_found_after_timeout"
                payload["recommended_action"] = (
                    "Confirm the endpoint is InService, send more traffic, wait a few minutes, then rerun "
                    "`python -m src.check_data_capture --wait`."
                )
                write_metadata(config, "data_capture_check", payload)
            return payload

        print(f"No capture files found yet under {capture_s3_uri}. Waiting {poll_seconds}s...")
        time.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args()
    print(
        json.dumps(
            check_data_capture(
                wait=args.wait,
                timeout_seconds=args.timeout_seconds,
                poll_seconds=args.poll_seconds,
            ),
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
