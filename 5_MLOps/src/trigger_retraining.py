"""Trigger or recommend retraining depending on ENABLE_AUTOMATIC_RETRAINING."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, write_metadata


def trigger_retraining() -> dict[str, object]:
    config = load_config(validate=True)
    if not config.enable_automatic_retraining:
        payload = {
            "status": "skipped",
            "reason": "ENABLE_AUTOMATIC_RETRAINING=false",
            "recommendation": "Review evidence, approve retraining, then enable the flag for controlled execution.",
        }
        write_metadata(config, "retraining_decision", payload)
        return payload

    clients = create_clients(config)
    response = clients.sagemaker.start_pipeline_execution(PipelineName=config.pipeline_name)
    payload = {
        "status": "started",
        "pipeline_name": config.pipeline_name,
        "pipeline_execution_arn": response["PipelineExecutionArn"],
    }
    write_metadata(config, "retraining_decision", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(trigger_retraining(), indent=2, default=str))


if __name__ == "__main__":
    main()

