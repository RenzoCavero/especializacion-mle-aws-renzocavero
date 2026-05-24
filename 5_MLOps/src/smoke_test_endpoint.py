"""Invoke the lab endpoint with a valid payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .aws_clients import create_clients
from .config import load_config, write_metadata


DEFAULT_PAYLOAD = {
    "record_id": "smoke-00001",
    "age": 41.0,
    "monthly_spend": 76.2,
    "support_tickets": 1,
    "tenure_months": 18.0,
    "late_payments": 0,
    "plan_type": "standard",
    "region": "north",
}


def smoke_test(payload: dict | None = None) -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    payload = payload or DEFAULT_PAYLOAD
    endpoint_description = clients.sagemaker.describe_endpoint(EndpointName=config.endpoint_name)
    endpoint_status = endpoint_description.get("EndpointStatus")
    if endpoint_status != "InService":
        failure_reason = endpoint_description.get("FailureReason", "")
        raise RuntimeError(
            f"Endpoint {config.endpoint_name} is not InService. "
            f"Current status: {endpoint_status}. {failure_reason}"
        )
    response = clients.sagemaker_runtime.invoke_endpoint(
        EndpointName=config.endpoint_name,
        Body=json.dumps(payload),
        ContentType="application/json",
        Accept="application/json",
    )
    body = response["Body"].read().decode("utf-8")
    parsed = json.loads(body)
    first = parsed[0] if isinstance(parsed, list) and parsed else parsed
    if not isinstance(first, dict) or "prediction" not in first:
        raise ValueError(f"Unexpected endpoint response: {body}")
    result = {"endpoint_name": config.endpoint_name, "request": payload, "response": parsed, "raw_response": body}
    write_metadata(config, "smoke_test", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-file", default="")
    args = parser.parse_args()
    payload = None
    if args.payload_file:
        payload = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    print(json.dumps(smoke_test(payload), indent=2))


if __name__ == "__main__":
    main()
