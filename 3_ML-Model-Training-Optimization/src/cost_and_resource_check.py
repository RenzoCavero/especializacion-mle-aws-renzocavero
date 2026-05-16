from __future__ import annotations

import json
import logging

from src.aws_clients import client, list_s3_keys
from src.config import get_config
from src.logging_utils import configure_logging


LOGGER = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    sm = client(config, "sagemaker")

    report = {
        "cost_guardrails": {
            "processing_instance_type": config.processing_instance_type,
            "training_instance_type": config.training_instance_type,
            "hpo_max_jobs": config.hpo_max_jobs,
            "hpo_max_parallel_jobs": config.hpo_max_parallel_jobs,
            "autopilot_max_candidates": config.autopilot_max_candidates,
            "online_store_enabled": config.enable_online_store,
            "offline_store_s3_uri": config.offline_store_s3_uri,
            "no_persistent_endpoints_expected": True,
        },
        "active_processing_jobs": sm.list_processing_jobs(
            StatusEquals="InProgress",
            NameContains=config.resource_prefix,
            MaxResults=20,
        ).get("ProcessingJobSummaries", []),
        "active_training_jobs": sm.list_training_jobs(
            StatusEquals="InProgress",
            NameContains=config.resource_prefix,
            MaxResults=20,
        ).get("TrainingJobSummaries", []),
        "active_hpo_jobs": sm.list_hyper_parameter_tuning_jobs(
            StatusEquals="InProgress",
            NameContains=config.resource_prefix,
            MaxResults=20,
        ).get("HyperParameterTuningJobSummaries", []),
        "active_autopilot_jobs": sm.list_auto_ml_jobs(
            StatusEquals="InProgress",
            NameContains=config.resource_prefix[:11].rstrip("-"),
            MaxResults=20,
        ).get("AutoMLJobSummaries", []),
        "endpoints_with_lab_prefix": sm.list_endpoints(
            NameContains=config.resource_prefix,
            MaxResults=20,
        ).get("Endpoints", []),
        "sample_s3_outputs": {
            "reports": list_s3_keys(config, config.reports_s3_uri, max_keys=10),
            "metrics": list_s3_keys(config, config.metrics_s3_uri, max_keys=10),
            "metadata": list_s3_keys(config, config.metadata_s3_uri, max_keys=10),
        },
    }
    local_path = config.local_outputs_dir / "cost_and_resource_check.json"
    local_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    LOGGER.info("Cost/resource report written to %s", local_path)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
