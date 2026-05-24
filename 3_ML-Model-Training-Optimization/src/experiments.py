from __future__ import annotations

import logging
from botocore.exceptions import ClientError

from src.aws_clients import client


LOGGER = logging.getLogger(__name__)


def ensure_experiment(config, experiment_name: str) -> None:
    sm = client(config, "sagemaker")
    try:
        sm.describe_experiment(ExperimentName=experiment_name)
        return
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"ResourceNotFound", "ValidationException"}:
            raise
    sm.create_experiment(
        ExperimentName=experiment_name,
        Description="Tema 3 churn training optimization experiment.",
        Tags=[
            {"Key": "Project", "Value": "MLModelTrainingOptimization"},
            {"Key": "Environment", "Value": "Lab"},
            {"Key": "ManagedBy", "Value": "Scripts"},
        ],
    )
    LOGGER.info("Created SageMaker Experiment %s", experiment_name)


def ensure_trial(config, experiment_name: str, trial_name: str) -> None:
    sm = client(config, "sagemaker")
    try:
        sm.describe_trial(TrialName=trial_name)
        return
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"ResourceNotFound", "ValidationException"}:
            raise
    sm.create_trial(
        TrialName=trial_name,
        ExperimentName=experiment_name,
        Tags=[
            {"Key": "Project", "Value": "MLModelTrainingOptimization"},
            {"Key": "Environment", "Value": "Lab"},
        ],
    )
    LOGGER.info("Created SageMaker Trial %s", trial_name)


def experiment_config(config, trial_name: str, display_name: str) -> dict[str, str]:
    ensure_experiment(config, config.experiment_name)
    ensure_trial(config, config.experiment_name, trial_name)
    return {
        "ExperimentName": config.experiment_name,
        "TrialName": trial_name,
        "TrialComponentDisplayName": display_name,
    }
