"""Send drifted synthetic traffic to the SageMaker endpoint."""

from __future__ import annotations

import argparse
import json
import time

from .aws_clients import create_clients
from .config import load_config, write_metadata
from .simulate_traffic import _load_records


def send_drift(limit: int = 25, sleep_seconds: float = 0.0) -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    path = config.local_cache_dir / "inference_drift.jsonl"
    if not path.exists():
        raise FileNotFoundError("Drift traffic data not found. Run: make data")
    records = _load_records(path, limit)
    for record in records:
        response = clients.sagemaker_runtime.invoke_endpoint(
            EndpointName=config.endpoint_name,
            Body=json.dumps(record),
            ContentType="application/json",
            Accept="application/json",
        )
        response["Body"].read()
        if sleep_seconds:
            time.sleep(sleep_seconds)
    payload = {
        "endpoint_name": config.endpoint_name,
        "records_sent": len(records),
        "traffic_type": "drift",
        "drift_features": ["monthly_spend", "support_tickets", "late_payments", "region", "plan_type"],
        "monitoring_note": "Model Monitor schedules may need one or more periods before violations appear.",
    }
    write_metadata(config, "traffic_drift", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    args = parser.parse_args()
    print(json.dumps(send_drift(limit=args.limit, sleep_seconds=args.sleep_seconds), indent=2))


if __name__ == "__main__":
    main()
