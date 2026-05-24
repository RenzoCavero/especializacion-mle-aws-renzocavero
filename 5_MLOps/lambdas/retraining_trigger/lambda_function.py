"""Trigger retraining only when the guardrail explicitly allows it."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import boto3


def lambda_handler(event, context):
    enabled = os.getenv("ENABLE_AUTOMATIC_RETRAINING", "false").lower() == "true"
    pipeline_name = os.getenv("PIPELINE_NAME", "")
    result = {
        "action": "retraining",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "automatic_retraining_enabled": enabled,
        "pipeline_name": pipeline_name,
    }
    if not enabled:
        result["status"] = "skipped"
        result["reason"] = "ENABLE_AUTOMATIC_RETRAINING=false"
        return result
    if not pipeline_name:
        result["status"] = "failed"
        result["reason"] = "PIPELINE_NAME is missing"
        return result
    response = boto3.client("sagemaker").start_pipeline_execution(PipelineName=pipeline_name)
    result["status"] = "started"
    result["pipeline_execution_arn"] = response["PipelineExecutionArn"]
    return result

