from __future__ import annotations

import logging
from datetime import datetime, timezone

from sagemaker.inputs import TrainingInput
from sagemaker.parameter import CategoricalParameter, ContinuousParameter, IntegerParameter
from sagemaker.tuner import HyperparameterTuner

from src.aws_clients import client, copy_s3_object
from src.config import get_config
from src.experiments import experiment_config
from src.instance_types import is_resource_limit_error, job_name_with_instance
from src.logging_utils import configure_logging
from src.state import update_state
from src.submit_training_job import build_estimator


LOGGER = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    timestamp = datetime.now(timezone.utc).strftime("%m%d%H%M%S")
    base_tuning_job_name = f"{config.resource_prefix[:8]}-hpo-{timestamp}"
    inputs = {
        "train": TrainingInput(f"{config.train_s3_uri}/train.csv", content_type="text/csv"),
        "validation": TrainingInput(f"{config.validation_s3_uri}/validation.csv", content_type="text/csv"),
    }

    selected_instance_type = None
    tuning_job_name = None
    last_quota_error: Exception | None = None
    for instance_type in config.training_instance_candidates:
        tuning_job_name = job_name_with_instance(base_tuning_job_name, instance_type, max_length=32)
        estimator = build_estimator(
            config,
            config.hpo_output_s3_uri,
            f"{config.resource_prefix}-hpo-training",
            hyperparameters={"random-state": 42},
            instance_type=instance_type,
        )
        tuner = HyperparameterTuner(
            estimator=estimator,
            objective_metric_name="validation:f1",
            hyperparameter_ranges={
                "C": ContinuousParameter(0.01, 10.0, scaling_type="Logarithmic"),
                "max-iter": IntegerParameter(150, 450),
                "class-weight": CategoricalParameter(["balanced", "none"]),
            },
            metric_definitions=estimator.metric_definitions,
            objective_type="Maximize",
            max_jobs=config.hpo_max_jobs,
            max_parallel_jobs=config.hpo_max_parallel_jobs,
            base_tuning_job_name=f"{config.resource_prefix[:16]}-hpo",
        )
        try:
            LOGGER.info("Submitting HPO job %s on %s", tuning_job_name, instance_type)
            tuner.fit(
                inputs,
                job_name=tuning_job_name,
                wait=config.wait_for_jobs,
                logs=True,
                experiment_config=experiment_config(config, f"{config.resource_prefix}-hpo-trial", tuning_job_name),
            )
            selected_instance_type = instance_type
            break
        except Exception as exc:
            if not is_resource_limit_error(exc):
                raise
            last_quota_error = exc
            LOGGER.warning(
                "Training instance %s is not available for HPO due to service quota. Trying next candidate.",
                instance_type,
            )
    if not selected_instance_type or not tuning_job_name:
        raise RuntimeError(
            "No HPO training instance type was available. Update TRAINING_INSTANCE_TYPE_FALLBACKS "
            "or request a SageMaker Training quota increase."
        ) from last_quota_error

    sm = client(config, "sagemaker")
    description = sm.describe_hyper_parameter_tuning_job(HyperParameterTuningJobName=tuning_job_name)
    best_training = description.get("BestTrainingJob", {}) if config.wait_for_jobs else {}
    best_training_job_name = best_training.get("TrainingJobName")
    best_metric = best_training.get("FinalHyperParameterTuningJobObjectiveMetric", {}).get("Value")
    best_model_artifact = None
    if best_training_job_name:
        training_description = sm.describe_training_job(TrainingJobName=best_training_job_name)
        best_model_artifact = training_description["ModelArtifacts"]["S3ModelArtifacts"]
        copy_s3_object(config, best_model_artifact, config.best_model_s3_uri)
        best_model_artifact = config.best_model_s3_uri

    update_state(
        hpo_job_name=tuning_job_name,
        best_training_job_name=best_training_job_name,
        hpo_best_objective_metric=best_metric,
        best_model_artifact_s3_uri=best_model_artifact,
        hpo_training_instance_type=selected_instance_type,
    )
    LOGGER.info("HPO job submitted: %s on %s", tuning_job_name, selected_instance_type)
    LOGGER.info("Best training job: %s", best_training_job_name)
    LOGGER.info("Best model artifact copied to: %s", best_model_artifact)


if __name__ == "__main__":
    main()
