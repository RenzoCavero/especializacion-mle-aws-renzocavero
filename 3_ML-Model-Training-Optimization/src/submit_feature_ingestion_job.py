from __future__ import annotations

import logging
from datetime import datetime, timezone

from sagemaker.processing import ProcessingInput, ProcessingOutput
from sagemaker.sklearn.processing import SKLearnProcessor

from src.aws_clients import client, download_file, sagemaker_session
from src.config import get_config, s3_join, sdk_local_path
from src.experiments import experiment_config
from src.instance_types import is_resource_limit_error, job_name_with_instance
from src.logging_utils import configure_logging
from src.state import update_state


LOGGER = logging.getLogger(__name__)
SRC_LIB_PATH = "/opt/ml/processing/code/src"


def build_processor(config, instance_type: str) -> SKLearnProcessor:
    return SKLearnProcessor(
        framework_version="1.2-1",
        role=config.sagemaker_execution_role_arn,
        instance_type=instance_type,
        instance_count=config.processing_instance_count,
        sagemaker_session=sagemaker_session(config),
        base_job_name=f"{config.resource_prefix}-feature-ingestion",
    )


def tag_feature_group_lineage(config) -> None:
    try:
        sm = client(config, "sagemaker")
        response = sm.describe_feature_group(FeatureGroupName=config.feature_group_name)
        feature_group_arn = response.get("FeatureGroupArn")
        if not feature_group_arn:
            return
        sm.add_tags(
            ResourceArn=feature_group_arn,
            Tags=[
                {"Key": "SourceRawS3Uri", "Value": config.raw_data_s3_uri},
                {"Key": "SourceCleanedS3Uri", "Value": config.cleaned_data_s3_uri},
                {"Key": "SourceCuratedS3Uri", "Value": config.curated_features_s3_uri},
                {"Key": "FeatureLineageS3Uri", "Value": config.feature_lineage_s3_uri},
            ],
        )
    except Exception as exc:  # noqa: BLE001 - tagging is helpful lineage metadata, not core ingestion.
        LOGGER.warning("Could not add lineage tags to Feature Group: %s", exc)


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    base_job_name = f"{config.resource_prefix}-feature-ingestion-{timestamp}"
    metadata_s3_uri = s3_join(config.s3_bucket_name, "feature-store", "ingestion", "metadata")
    lineage_s3_uri = s3_join(config.s3_bucket_name, "feature-store", "ingestion", "metadata", "feature_ingestion_lineage.json")
    local_metadata_path = config.local_outputs_dir / "feature_ingestion_metadata.json"
    local_lineage_path = config.local_outputs_dir / "feature_ingestion_lineage.json"

    run_kwargs = {
        "code": sdk_local_path("processing", "feature_ingestion_entrypoint.py"),
        "inputs": [
            ProcessingInput(
                source=sdk_local_path("src"),
                destination=SRC_LIB_PATH,
                input_name="src-source",
            ),
            ProcessingInput(
                source=config.curated_features_s3_uri,
                destination="/opt/ml/processing/curated",
                input_name="curated-features",
            ),
        ],
        "outputs": [
            ProcessingOutput(
                output_name="metadata",
                source="/opt/ml/processing/output/metadata",
                destination=metadata_s3_uri,
            )
        ],
        "arguments": [
            "--input-data",
            "/opt/ml/processing/curated",
            "--feature-group-name",
            config.feature_group_name,
            "--aws-region",
            config.aws_region,
            "--source-raw-s3-uri",
            config.raw_data_s3_uri,
            "--source-cleaned-s3-uri",
            config.cleaned_data_s3_uri,
            "--source-curated-s3-uri",
            config.curated_features_s3_uri,
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
            LOGGER.info("Submitting Feature Store ingestion Processing Job %s on %s", job_name, instance_type)
            processor.run(
                **run_kwargs,
                job_name=job_name,
                experiment_config=experiment_config(config, f"{config.resource_prefix}-feature-ingestion", job_name),
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
            "No Processing Job instance type was available for Feature Store ingestion."
        ) from last_quota_error

    if config.wait_for_jobs:
        download_file(config, f"{metadata_s3_uri}/feature_ingestion_metadata.json", str(local_metadata_path))
        download_file(config, f"{metadata_s3_uri}/feature_ingestion_lineage.json", str(local_lineage_path))
    tag_feature_group_lineage(config)

    update_state(
        feature_ingestion_job_name=job_name,
        feature_ingestion_instance_type=selected_instance_type,
        feature_ingestion_metadata_s3_uri=f"{metadata_s3_uri}/feature_ingestion_metadata.json",
        feature_ingestion_metadata_local_path=str(local_metadata_path),
        feature_ingestion_lineage_s3_uri=lineage_s3_uri,
        feature_ingestion_lineage_local_path=str(local_lineage_path),
    )
    LOGGER.info("Feature Store ingestion Processing Job submitted: %s on %s", job_name, selected_instance_type)


if __name__ == "__main__":
    main()
