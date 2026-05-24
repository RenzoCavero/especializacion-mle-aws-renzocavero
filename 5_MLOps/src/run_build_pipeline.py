"""Start a SageMaker Pipeline execution."""

from __future__ import annotations

import argparse
import json
import time

from .aws_clients import create_clients
from .config import load_config, write_metadata


def start_pipeline(wait: bool = False, poll_seconds: int = 30) -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    response = clients.sagemaker.start_pipeline_execution(
        PipelineName=config.pipeline_name,
        PipelineParameters=[
            {"Name": "InputDataUri", "Value": f"{config.raw_data_s3_uri}/churn_train.csv"},
            {"Name": "F1Threshold", "Value": str(config.f1_threshold)},
            {"Name": "AUCThreshold", "Value": str(config.auc_threshold)},
            {"Name": "ModelPackageGroupName", "Value": config.model_package_group_name},
        ],
    )
    execution_arn = response["PipelineExecutionArn"]
    result: dict[str, object] = {"pipeline_name": config.pipeline_name, "pipeline_execution_arn": execution_arn}

    if wait:
        while True:
            status = clients.sagemaker.describe_pipeline_execution(PipelineExecutionArn=execution_arn)
            result["status"] = status.get("PipelineExecutionStatus")
            if result["status"] in {"Succeeded", "Failed", "Stopped"}:
                result["description"] = status
                break
            print(f"Pipeline status: {result['status']}. Waiting {poll_seconds}s...")
            time.sleep(poll_seconds)

    write_metadata(config, "pipeline_execution", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(start_pipeline(wait=args.wait, poll_seconds=args.poll_seconds), indent=2, default=str))


if __name__ == "__main__":
    main()

