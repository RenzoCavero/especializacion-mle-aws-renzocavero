from __future__ import annotations

import logging
from datetime import datetime, timezone

from sagemaker.inputs import TrainingInput
from sagemaker.sklearn.estimator import SKLearn

from src.aws_clients import sagemaker_session
from src.config import get_config, sdk_local_path
from src.experiments import experiment_config
from src.instance_types import is_resource_limit_error, job_name_with_instance
from src.logging_utils import configure_logging
from src.state import update_state


LOGGER = logging.getLogger(__name__)


METRIC_DEFINITIONS = [
    {"Name": "validation:accuracy", "Regex": r"validation:accuracy=([0-9\\.]+)"},
    {"Name": "validation:precision", "Regex": r"validation:precision=([0-9\\.]+)"},
    {"Name": "validation:recall", "Regex": r"validation:recall=([0-9\\.]+)"},
    {"Name": "validation:f1", "Regex": r"validation:f1=([0-9\\.]+)"},
    {"Name": "validation:roc_auc", "Regex": r"validation:roc_auc=([0-9\\.]+)"},
]


def build_estimator(
    config,
    output_path: str,
    base_job_name: str,
    hyperparameters: dict | None = None,
    instance_type: str | None = None,
) -> SKLearn:
    return SKLearn(
        entry_point="train.py",
        source_dir=sdk_local_path("training"),
        role=config.sagemaker_execution_role_arn,
        framework_version="1.2-1",
        py_version="py3",
        instance_type=instance_type or config.training_instance_type,
        instance_count=config.training_instance_count,
        output_path=output_path,
        code_location=f"s3://{config.s3_bucket_name}/code",
        base_job_name=base_job_name,
        metric_definitions=METRIC_DEFINITIONS,
        hyperparameters=hyperparameters
        or {
            "C": 1.0,
            "max-iter": 250,
            "class-weight": "balanced",
            "random-state": 42,
        },
        sagemaker_session=sagemaker_session(config),
    )


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    base_job_name = f"{config.resource_prefix}-baseline-{timestamp}"
    inputs = {
        "train": TrainingInput(f"{config.train_s3_uri}/train.csv", content_type="text/csv"),
        "validation": TrainingInput(f"{config.validation_s3_uri}/validation.csv", content_type="text/csv"),
    }

    selected_instance_type = None
    job_name = None
    estimator = None
    last_quota_error: Exception | None = None
    for instance_type in config.training_instance_candidates:
        job_name = job_name_with_instance(base_job_name, instance_type)
        estimator = build_estimator(
            config,
            config.baseline_output_s3_uri,
            f"{config.resource_prefix}-baseline",
            instance_type=instance_type,
        )
        try:
            LOGGER.info("Submitting baseline Training Job %s on %s", job_name, instance_type)
            estimator.fit(
                inputs=inputs,
                job_name=job_name,
                wait=config.wait_for_jobs,
                logs=True,
                experiment_config=experiment_config(config, f"{config.resource_prefix}-baseline-trial", job_name),
            )
            selected_instance_type = instance_type
            break
        except Exception as exc:
            if not is_resource_limit_error(exc):
                raise
            last_quota_error = exc
            LOGGER.warning(
                "Training instance %s is not available due to service quota. Trying next candidate.",
                instance_type,
            )
    if not selected_instance_type or not job_name or not estimator:
        raise RuntimeError(
            "No Training Job instance type was available. Update TRAINING_INSTANCE_TYPE_FALLBACKS "
            "or request a SageMaker Training quota increase."
        ) from last_quota_error

    model_artifact = estimator.model_data
    update_state(
        baseline_training_job_name=job_name,
        baseline_model_artifact_s3_uri=model_artifact,
        baseline_training_instance_type=selected_instance_type,
    )
    LOGGER.info("Baseline Training Job submitted: %s on %s", job_name, selected_instance_type)
    LOGGER.info("Baseline model artifact: %s", model_artifact)


if __name__ == "__main__":
    main()
