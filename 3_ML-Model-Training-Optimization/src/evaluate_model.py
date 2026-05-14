from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone

from sagemaker.processing import ProcessingInput, ProcessingOutput
from sagemaker.sklearn.processing import SKLearnProcessor

from src.aws_clients import download_file, sagemaker_session
from src.config import get_config, s3_join, sdk_local_path
from src.experiments import experiment_config
from src.instance_types import is_resource_limit_error, job_name_with_instance
from src.logging_utils import configure_logging
from src.state import load_state, update_state


LOGGER = logging.getLogger(__name__)
PROCESSING_LIB_PATH = "/opt/ml/processing/lib"


def build_processor(config, instance_type: str) -> SKLearnProcessor:
    return SKLearnProcessor(
        framework_version="1.2-1",
        role=config.sagemaker_execution_role_arn,
        instance_type=instance_type,
        instance_count=config.processing_instance_count,
        sagemaker_session=sagemaker_session(config),
        base_job_name=f"{config.resource_prefix}-evaluation",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit a SageMaker Processing Job for model evaluation.")
    parser.add_argument("--model-name", choices=["baseline", "optimized"], default="baseline")
    parser.add_argument("--model-artifact-s3-uri", default=None)
    args = parser.parse_args()

    configure_logging()
    config = get_config()
    config.require_aws_fields()
    state = load_state()
    model_artifact = args.model_artifact_s3_uri
    if model_artifact is None:
        key = "baseline_model_artifact_s3_uri" if args.model_name == "baseline" else "best_model_artifact_s3_uri"
        model_artifact = state.get(key)
    if not model_artifact:
        raise ValueError(f"No model artifact found for {args.model_name}. Run training/HPO first.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    base_job_name = f"{config.resource_prefix}-eval-{args.model_name}-{timestamp}"
    evaluation_s3_uri = s3_join(config.s3_bucket_name, "evaluation", args.model_name)
    report_s3_uri = s3_join(config.s3_bucket_name, "reports", args.model_name)

    run_kwargs = {
        "code": sdk_local_path("processing", "evaluation_entrypoint.py"),
        "inputs": [
            ProcessingInput(
                source=sdk_local_path("processing"),
                destination=PROCESSING_LIB_PATH,
                input_name="processing-source",
            ),
            ProcessingInput(
                source=f"{config.test_s3_uri}/test.csv",
                destination="/opt/ml/processing/test",
                input_name="test-data",
            ),
            ProcessingInput(
                source=model_artifact,
                destination="/opt/ml/processing/model",
                input_name="model-artifact",
            ),
        ],
        "outputs": [
            ProcessingOutput(output_name="evaluation", source="/opt/ml/processing/evaluation", destination=evaluation_s3_uri),
            ProcessingOutput(output_name="reports", source="/opt/ml/processing/reports", destination=report_s3_uri),
        ],
        "arguments": [
            "--test-data",
            "/opt/ml/processing/test",
            "--model-artifact",
            "/opt/ml/processing/model",
            "--evaluation-output",
            "/opt/ml/processing/evaluation",
            "--reports-output",
            "/opt/ml/processing/reports",
            "--model-name",
            args.model_name,
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
            LOGGER.info("Submitting Evaluation Processing Job %s on %s", job_name, instance_type)
            processor.run(
                **run_kwargs,
                job_name=job_name,
                experiment_config=experiment_config(
                    config,
                    f"{config.resource_prefix}-{args.model_name}-evaluation",
                    job_name,
                ),
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
            "No evaluation Processing Job instance type was available. Update PROCESSING_INSTANCE_TYPE_FALLBACKS "
            "or request a SageMaker Processing quota increase."
        ) from last_quota_error

    metrics_s3_uri = f"{evaluation_s3_uri}/evaluation_metrics.json"
    local_dir = config.local_outputs_dir / "evaluation" / args.model_name
    local_dir.mkdir(parents=True, exist_ok=True)
    local_metrics = local_dir / "evaluation_metrics.json"
    if config.wait_for_jobs:
        download_file(config, metrics_s3_uri, str(local_metrics))

    update = {
        f"{args.model_name}_evaluation_job_name": job_name,
        f"{args.model_name}_metrics_s3_uri": metrics_s3_uri,
        f"{args.model_name}_metrics_local_path": str(local_metrics),
        f"{args.model_name}_report_s3_uri": f"{report_s3_uri}/{args.model_name}_evaluation_report.md",
        f"{args.model_name}_evaluation_instance_type": selected_instance_type,
    }
    update_state(**update)
    LOGGER.info("Evaluation Processing Job submitted: %s on %s", job_name, selected_instance_type)
    LOGGER.info("Evaluation metrics: %s", metrics_s3_uri)


if __name__ == "__main__":
    main()
