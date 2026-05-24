"""Send normal synthetic traffic to the SageMaker endpoint."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .aws_clients import create_clients
from .config import load_config, write_metadata


def _load_records(path: Path, limit: int) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
            if len(records) >= limit:
                break
    return records


def send_traffic(limit: int = 25, sleep_seconds: float = 0.0) -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    path = config.local_cache_dir / "inference_normal.jsonl"
    if not path.exists():
        raise FileNotFoundError("Normal traffic data not found. Run: make data")
    records = _load_records(path, limit)
    responses = []
    for record in records:
        response = clients.sagemaker_runtime.invoke_endpoint(
            EndpointName=config.endpoint_name,
            Body=json.dumps(record),
            ContentType="application/json",
            Accept="application/json",
        )
        responses.append(response["Body"].read().decode("utf-8"))
        if sleep_seconds:
            time.sleep(sleep_seconds)

    payload = {
        "endpoint_name": config.endpoint_name,
        "records_sent": len(records),
        "traffic_type": "normal",
        "data_capture_note": "Captured data may take time to appear in S3.",
    }
    write_metadata(config, "traffic_normal", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    args = parser.parse_args()
    print(json.dumps(send_traffic(limit=args.limit, sleep_seconds=args.sleep_seconds), indent=2))


if __name__ == "__main__":
    main()

