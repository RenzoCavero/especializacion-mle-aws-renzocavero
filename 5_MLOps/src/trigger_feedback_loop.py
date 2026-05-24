"""Start the Step Functions feedback loop with an example input."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata


def trigger(input_payload: dict | None = None) -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    metadata = read_metadata(config, "feedback_loop")
    state_machine_arn = metadata.get("state_machine_arn")
    if not state_machine_arn:
        raise ValueError("No state_machine_arn found. Run make create-feedback-loop first.")

    payload = input_payload or {
        "alarm_name": config.alarm_name,
        "endpoint_name": config.endpoint_name,
        "violations_count": 2,
        "severity": "medium",
        "source": "manual-lab-trigger",
    }
    response = clients.stepfunctions.start_execution(
        stateMachineArn=str(state_machine_arn),
        input=json.dumps(payload),
    )
    result = {
        "state_machine_arn": state_machine_arn,
        "execution_arn": response["executionArn"],
        "input": payload,
    }
    write_metadata(config, "feedback_loop_execution", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-json", default="")
    args = parser.parse_args()
    payload = json.loads(args.input_json) if args.input_json else None
    print(json.dumps(trigger(payload), indent=2, default=str))


if __name__ == "__main__":
    main()

