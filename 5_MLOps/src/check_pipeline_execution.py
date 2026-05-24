"""Check SageMaker Pipeline execution status."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata


def build_recommendations(steps: list[dict[str, object]]) -> list[str]:
    recommendations: list[str] = []
    failure_text = "\n".join(str(step.get("FailureReason", "")) for step in steps)
    lower = failure_text.lower()
    if "training-job/" in lower and "not available in this region" in lower:
        recommendations.append(
            "Training instance is not available in this region. Run "
            "`python -m src.compute --workload training --inventory --limit 0` "
            "and use only instance types with positive training quota."
        )
    if "sagemaker_resource_limit" in lower or "service limit" in lower:
        recommendations.append(
            "SageMaker quota limit reached. Check Service Quotas with "
            "`python -m src.compute --workload training --inventory --limit 0` "
            "or request a quota increase for the failing workload."
        )
    for step in steps:
        if step.get("StepName") != "QualityGate":
            continue
        outcome = step.get("Metadata", {}).get("Condition", {}).get("Outcome")
        if outcome == "False":
            recommendations.append(
                "QualityGate outcome was False, so RegisterModel did not run. "
                "Review evaluation metrics, then rerun `python -m src.lab_runner step 02` "
                "and `python -m src.lab_runner step 05` before step 06."
            )
    return recommendations


def check_execution(execution_arn: str | None = None) -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    if not execution_arn:
        execution_arn = read_metadata(config, "pipeline_execution").get("pipeline_execution_arn")
    if not execution_arn:
        raise ValueError("No pipeline execution ARN provided and no local metadata found.")

    description = clients.sagemaker.describe_pipeline_execution(PipelineExecutionArn=execution_arn)
    steps = clients.sagemaker.list_pipeline_execution_steps(PipelineExecutionArn=execution_arn)
    execution_steps = steps.get("PipelineExecutionSteps", [])
    payload = {
        "pipeline_execution_arn": execution_arn,
        "status": description.get("PipelineExecutionStatus"),
        "description": description,
        "steps": execution_steps,
        "recommendations": build_recommendations(execution_steps),
    }
    write_metadata(config, "pipeline_execution_status", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-arn", default="")
    args = parser.parse_args()
    print(json.dumps(check_execution(args.execution_arn or None), indent=2, default=str))


if __name__ == "__main__":
    main()
