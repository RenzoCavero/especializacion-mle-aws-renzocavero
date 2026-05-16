from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone

from src.aws_clients import client
from src.config import get_config, s3_join
from src.feature_schema import TARGET_COLUMN
from src.logging_utils import configure_logging
from src.state import update_state


LOGGER = logging.getLogger(__name__)


TERMINAL_STATUSES = {"Completed", "Failed", "Stopped"}


def wait_for_autopilot_job(config, job_name: str, poll_seconds: int = 60) -> dict:
    sm = client(config, "sagemaker")
    while True:
        response = sm.describe_auto_ml_job_v2(AutoMLJobName=job_name)
        status = response.get("AutoMLJobStatus")
        secondary_status = response.get("AutoMLJobSecondaryStatus")
        LOGGER.info("Autopilot job %s status: %s / %s", job_name, status, secondary_status)
        if status in TERMINAL_STATUSES:
            if status != "Completed":
                failure_reason = response.get("FailureReason", "No failure reason returned.")
                raise RuntimeError(f"Autopilot job {job_name} ended with {status}: {failure_reason}")
            return response
        time.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit a small SageMaker Autopilot tabular job.")
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait until the AutoML job completes. By default the script submits the job and returns.",
    )
    args = parser.parse_args()

    configure_logging()
    config = get_config()
    config.require_aws_fields()

    timestamp = datetime.now(timezone.utc).strftime("%m%d%H%M%S")
    job_prefix = config.resource_prefix[:11].rstrip("-")
    job_name = f"{job_prefix}-automl-{timestamp}"
    output_path = s3_join(config.s3_bucket_name, "automl", "output")
    request = {
        "AutoMLJobName": job_name,
        "RoleArn": config.sagemaker_execution_role_arn,
        "AutoMLJobInputDataConfig": [
            {
                "ChannelType": "training",
                "ContentType": "text/csv;header=present",
                "CompressionType": "None",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": config.train_s3_uri,
                    }
                },
            },
            {
                "ChannelType": "validation",
                "ContentType": "text/csv;header=present",
                "CompressionType": "None",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": config.validation_s3_uri,
                    }
                },
            },
        ],
        "OutputDataConfig": {"S3OutputPath": output_path},
        "AutoMLProblemTypeConfig": {
            "TabularJobConfig": {
                "TargetAttributeName": TARGET_COLUMN,
                "ProblemType": "BinaryClassification",
                "Mode": config.autopilot_mode,
                "CompletionCriteria": {
                    "MaxCandidates": config.autopilot_max_candidates,
                    "MaxAutoMLJobRuntimeInSeconds": config.autopilot_max_runtime_seconds,
                },
            }
        },
        "AutoMLJobObjective": {"MetricName": "F1"},
        "Tags": [
            {"Key": "Project", "Value": "MLModelTrainingOptimization"},
            {"Key": "Environment", "Value": "Lab"},
            {"Key": "ManagedBy", "Value": "Scripts"},
        ],
    }
    LOGGER.info("Submitting Autopilot job %s", job_name)
    response = client(config, "sagemaker").create_auto_ml_job_v2(**request)
    state_update = {
        "autopilot_job_name": job_name,
        "autopilot_job_arn": response.get("AutoMLJobArn"),
        "autopilot_input_train_s3_uri": config.train_s3_uri,
        "autopilot_input_validation_s3_uri": config.validation_s3_uri,
        "autopilot_output_s3_uri": output_path,
        "autopilot_mode": config.autopilot_mode,
        "autopilot_max_candidates": config.autopilot_max_candidates,
    }

    if args.wait:
        description = wait_for_autopilot_job(config, job_name)
        best_candidate = description.get("BestCandidate", {})
        state_update.update(
            {
                "autopilot_best_candidate_name": best_candidate.get("CandidateName"),
                "autopilot_best_candidate_status": best_candidate.get("CandidateStatus"),
                "autopilot_best_candidate_objective": best_candidate.get("FinalAutoMLJobObjectiveMetric"),
            }
        )

    update_state(**state_update)
    LOGGER.info("Autopilot job submitted: %s", job_name)
    LOGGER.info("Autopilot output: %s", output_path)


if __name__ == "__main__":
    main()
