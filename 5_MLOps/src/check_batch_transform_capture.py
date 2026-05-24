"""Check Batch Transform outputs and batch Data Capture files."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

from .aws_clients import create_clients
from .config import load_config, write_metadata
from .check_data_capture import list_capture_objects


def _has_objects(listing: dict[str, Any]) -> bool:
    return int(listing.get("object_count", 0)) > 0


def check_batch_capture(wait: bool = False, timeout_seconds: int = 300, poll_seconds: int = 30) -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    deadline = time.time() + timeout_seconds

    while True:
        output_listing = list_capture_objects(clients.s3, config.batch_transform_output_s3_uri)
        capture_listing = list_capture_objects(clients.s3, config.batch_data_capture_s3_uri)
        output_found = _has_objects(output_listing)
        capture_found = _has_objects(capture_listing)
        payload = {
            "batch_transform_output_s3_uri": config.batch_transform_output_s3_uri,
            "batch_data_capture_s3_uri": config.batch_data_capture_s3_uri,
            "output_listing": output_listing,
            "capture_listing": capture_listing,
            "status": "batch_output_and_capture_found" if output_found and capture_found else "waiting_for_batch_output_or_capture",
            "note": (
                "For Batch Transform, Data Capture is job-scoped. Validate S3 outputs and the "
                "BatchDataCaptureConfig destination, not an endpoint Data Capture tab."
            ),
        }
        write_metadata(config, "batch_transform_capture", payload)
        if (output_found and capture_found) or not wait or time.time() >= deadline:
            if wait and not (output_found and capture_found):
                payload["status"] = "batch_output_or_capture_not_found_after_timeout"
                payload["recommended_action"] = "Check the transform job status and IAM permissions, then rerun this check."
                write_metadata(config, "batch_transform_capture", payload)
            return payload

        print("Batch output or capture files not found yet. Waiting 30s...")
        time.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(check_batch_capture(args.wait, args.timeout_seconds, args.poll_seconds), indent=2, default=str))


if __name__ == "__main__":
    main()
