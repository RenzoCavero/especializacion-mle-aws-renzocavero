from __future__ import annotations

import logging

from src.aws_clients import sagemaker_session
from src.config import get_config
from src.logging_utils import configure_logging
from src.state import update_state


LOGGER = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    session = sagemaker_session(config)
    pipeline = session.sagemaker_client.describe_pipeline(PipelineName=config.pipeline_name)
    LOGGER.info("Starting pipeline %s (%s)", config.pipeline_name, pipeline.get("PipelineArn"))
    response = session.sagemaker_client.start_pipeline_execution(
        PipelineName=config.pipeline_name,
        PipelineParameters=[
            {"Name": "InputDataS3Uri", "Value": config.feature_snapshot_s3_uri},
            {"Name": "CuratedFeaturesS3Uri", "Value": config.curated_features_s3_uri},
            {"Name": "FeatureSource", "Value": config.feature_data_source},
            {"Name": "AthenaOutputS3Uri", "Value": config.athena_query_results_s3_uri},
            {"Name": "ModelApprovalStatus", "Value": "PendingManualApproval"},
            {"Name": "MinF1ForRegistration", "Value": "0.50"},
        ],
    )
    update_state(pipeline_execution_arn=response["PipelineExecutionArn"])
    LOGGER.info("Started pipeline execution %s", response["PipelineExecutionArn"])


if __name__ == "__main__":
    main()
