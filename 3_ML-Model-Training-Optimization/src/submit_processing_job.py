from __future__ import annotations

import logging
from datetime import datetime, timezone

from sagemaker.processing import ProcessingInput, ProcessingOutput
from sagemaker.sklearn.processing import SKLearnProcessor

from src.aws_clients import download_file, sagemaker_session
from src.config import get_config, s3_join, sdk_local_path
from src.experiments import experiment_config
from src.instance_types import is_resource_limit_error, job_name_with_instance
from src.logging_utils import configure_logging
from src.state import update_state


LOGGER = logging.getLogger(__name__)
PROCESSING_LIB_PATH = "/opt/ml/processing/lib"


def build_processor(config, instance_type: str) -> SKLearnProcessor:
    return SKLearnProcessor(
        framework_version="1.2-1",
        role=config.sagemaker_execution_role_arn,
        instance_type=instance_type,
        instance_count=config.processing_instance_count,
        sagemaker_session=sagemaker_session(config),
        base_job_name=f"{config.resource_prefix}-processing",
    )


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    base_job_name = f"{config.resource_prefix}-processing-{timestamp}"
    outputs = [
        ProcessingOutput(output_name="train", source="/opt/ml/processing/output/train", destination=config.train_s3_uri),
        ProcessingOutput(
            output_name="validation",
            source="/opt/ml/processing/output/validation",
            destination=config.validation_s3_uri,
        ),
        ProcessingOutput(output_name="test", source="/opt/ml/processing/output/test", destination=config.test_s3_uri),
        ProcessingOutput(
            output_name="metadata",
            source="/opt/ml/processing/output/metadata",
            destination=s3_join(config.s3_bucket_name, "processing", "output", "metadata"),
        ),
    ]

    run_kwargs = {
        "code": sdk_local_path("processing", "processing_entrypoint.py"),
        "inputs": [
            ProcessingInput(
                source=sdk_local_path("processing"),
                destination=PROCESSING_LIB_PATH,
                input_name="processing-source",
            ),
            ProcessingInput(
                source=config.feature_snapshot_s3_uri,
                destination="/opt/ml/processing/input",
                input_name="feature-snapshot",
            ),
        ],
        "outputs": outputs,
        "arguments": [
            "--input-data",
            "/opt/ml/processing/input",
            "--train-output",
            "/opt/ml/processing/output/train",
            "--validation-output",
            "/opt/ml/processing/output/validation",
            "--test-output",
            "/opt/ml/processing/output/test",
            "--metadata-output",
            "/opt/ml/processing/output/metadata",
        ],
        "wait": config.wait_for_jobs,
        "logs": True,
    }

    selected_instance_type = None
    job_name = None
    last_quota_error: Exception | None = None
    for instance_type in config.processing_instance_candidates:
        job_name = job_name_with_instance(base_job_name, instance_type)
        processor = build_processor(config, instance_type)
        try:
            LOGGER.info("Submitting Processing Job %s on %s", job_name, instance_type)
            processor.run(
                **run_kwargs,
                job_name=job_name,
                experiment_config=experiment_config(config, f"{config.resource_prefix}-data-processing", job_name),
            )
            selected_instance_type = instance_type
            break
        except Exception as exc:
            if not is_resource_limit_error(exc):
                raise
            last_quota_error = exc
            LOGGER.warning(
                "Processing instance %s is not available due to service quota. Trying next candidate.",
                instance_type,
            )
    if not selected_instance_type or not job_name:
        raise RuntimeError(
            "No Processing Job instance type was available. Update PROCESSING_INSTANCE_TYPE_FALLBACKS "
            "or request a SageMaker Processing quota increase."
        ) from last_quota_error

    preprocessing_metadata_s3_uri = s3_join(
        config.s3_bucket_name,
        "processing",
        "output",
        "metadata",
        "preprocessing_metadata.json",
    )
    local_metadata_path = config.local_outputs_dir / "preprocessing_metadata.json"
    if config.wait_for_jobs:
        download_file(config, preprocessing_metadata_s3_uri, str(local_metadata_path))

    update_state(
        processing_job_name=job_name,
        train_s3_uri=config.train_s3_uri,
        validation_s3_uri=config.validation_s3_uri,
        test_s3_uri=config.test_s3_uri,
        preprocessing_metadata_s3_uri=preprocessing_metadata_s3_uri,
        preprocessing_metadata_local_path=str(local_metadata_path),
        processing_instance_type=selected_instance_type,
    )
    LOGGER.info("Processing Job submitted: %s on %s", job_name, selected_instance_type)


if __name__ == "__main__":
    main()
