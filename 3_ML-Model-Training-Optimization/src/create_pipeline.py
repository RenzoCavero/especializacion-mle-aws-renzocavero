from __future__ import annotations

import logging

from sagemaker.inputs import TrainingInput
from sagemaker.processing import ProcessingInput, ProcessingOutput
from sagemaker.sklearn.estimator import SKLearn
from sagemaker.sklearn.processing import SKLearnProcessor
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.conditions import ConditionGreaterThanOrEqualTo
from sagemaker.workflow.functions import JsonGet
from sagemaker.workflow.parameters import ParameterFloat, ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.properties import PropertyFile
from sagemaker.workflow.step_collections import RegisterModel
from sagemaker.workflow.steps import ProcessingStep, TrainingStep

from src.aws_clients import pipeline_session
from src.config import get_config, s3_join, sdk_local_path
from src.logging_utils import configure_logging
from src.state import load_state, update_state
from src.submit_training_job import METRIC_DEFINITIONS


LOGGER = logging.getLogger(__name__)
PROCESSING_LIB_PATH = "/opt/ml/processing/lib"


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    state = load_state()
    session = pipeline_session(config)
    processing_instance_type = state.get("processing_instance_type", config.processing_instance_type)
    training_instance_type = state.get("baseline_training_instance_type", config.training_instance_type)

    input_data = ParameterString(name="InputDataS3Uri", default_value=config.feature_snapshot_s3_uri)
    feature_source = ParameterString(name="FeatureSource", default_value=config.feature_data_source)
    athena_output_s3_uri = ParameterString(
        name="AthenaOutputS3Uri",
        default_value=config.athena_query_results_s3_uri,
    )
    model_approval_status = ParameterString(name="ModelApprovalStatus", default_value="PendingManualApproval")
    min_f1 = ParameterFloat(name="MinF1ForRegistration", default_value=0.50)

    processor = SKLearnProcessor(
        framework_version="1.2-1",
        role=config.sagemaker_execution_role_arn,
        instance_type=processing_instance_type,
        instance_count=config.processing_instance_count,
        sagemaker_session=session,
        base_job_name=f"{config.resource_prefix}-pipeline-processing",
    )
    processing_args = processor.run(
        code=sdk_local_path("processing", "processing_entrypoint.py"),
        inputs=[
            ProcessingInput(
                source=sdk_local_path("processing"),
                destination=PROCESSING_LIB_PATH,
                input_name="processing-source",
            ),
            ProcessingInput(source=input_data, destination="/opt/ml/processing/input", input_name="feature-snapshot"),
        ],
        outputs=[
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
                destination=s3_join(config.s3_bucket_name, "processing", "pipeline", "metadata"),
            ),
        ],
        arguments=[
            "--feature-source",
            feature_source,
            "--feature-group-name",
            config.feature_group_name,
            "--aws-region",
            config.aws_region,
            "--athena-output-s3-uri",
            athena_output_s3_uri,
            "--offline-store-max-wait-seconds",
            str(config.offline_store_max_wait_seconds),
            "--offline-store-poll-seconds",
            str(config.offline_store_poll_seconds),
        ]
        + (["--allow-snapshot-fallback"] if config.allow_feature_snapshot_fallback else []),
        wait=False,
    )
    step_process = ProcessingStep(name="ProcessChurnFeatures", step_args=processing_args)

    estimator = SKLearn(
        entry_point="train.py",
        source_dir=sdk_local_path("training"),
        role=config.sagemaker_execution_role_arn,
        framework_version="1.2-1",
        py_version="py3",
        instance_type=training_instance_type,
        instance_count=config.training_instance_count,
        output_path=s3_join(config.s3_bucket_name, "output", "pipeline"),
        code_location=s3_join(config.s3_bucket_name, "code"),
        base_job_name=f"{config.resource_prefix}-pipeline-train",
        metric_definitions=METRIC_DEFINITIONS,
        hyperparameters={"C": 1.0, "max-iter": 250, "class-weight": "balanced", "random-state": 42},
        sagemaker_session=session,
    )
    train_args = estimator.fit(
        inputs={
            "train": TrainingInput(
                s3_data=step_process.properties.ProcessingOutputConfig.Outputs["train"].S3Output.S3Uri,
                content_type="text/csv",
            ),
            "validation": TrainingInput(
                s3_data=step_process.properties.ProcessingOutputConfig.Outputs["validation"].S3Output.S3Uri,
                content_type="text/csv",
            ),
        },
        wait=False,
    )
    step_train = TrainingStep(name="TrainChurnBaseline", step_args=train_args)

    evaluation_report = PropertyFile(
        name="EvaluationReport",
        output_name="evaluation",
        path="evaluation.json",
    )
    eval_args = processor.run(
        code=sdk_local_path("processing", "evaluation_entrypoint.py"),
        inputs=[
            ProcessingInput(
                source=sdk_local_path("processing"),
                destination=PROCESSING_LIB_PATH,
                input_name="processing-source",
            ),
            ProcessingInput(
                source=step_process.properties.ProcessingOutputConfig.Outputs["test"].S3Output.S3Uri,
                destination="/opt/ml/processing/test",
                input_name="test-data",
            ),
            ProcessingInput(
                source=step_train.properties.ModelArtifacts.S3ModelArtifacts,
                destination="/opt/ml/processing/model",
                input_name="model-artifact",
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="evaluation",
                source="/opt/ml/processing/evaluation",
                destination=s3_join(config.s3_bucket_name, "evaluation", "pipeline"),
            ),
            ProcessingOutput(
                output_name="reports",
                source="/opt/ml/processing/reports",
                destination=s3_join(config.s3_bucket_name, "reports", "pipeline"),
            ),
        ],
        arguments=["--model-name", "pipeline-candidate"],
        wait=False,
    )
    step_eval = ProcessingStep(
        name="EvaluateChurnModel",
        step_args=eval_args,
        property_files=[evaluation_report],
    )

    step_register = RegisterModel(
        name="RegisterChurnModel",
        estimator=estimator,
        model_data=step_train.properties.ModelArtifacts.S3ModelArtifacts,
        content_types=["text/csv", "application/json"],
        response_types=["text/csv", "application/json"],
        inference_instances=["ml.m5.large"],
        transform_instances=["ml.m5.large"],
        model_package_group_name=config.model_package_group_name,
        approval_status=model_approval_status,
    )
    step_condition = ConditionStep(
        name="CheckF1BeforeRegister",
        conditions=[
            ConditionGreaterThanOrEqualTo(
                left=JsonGet(
                    step_name=step_eval.name,
                    property_file=evaluation_report,
                    json_path="classification_metrics.f1.value",
                ),
                right=min_f1,
            )
        ],
        if_steps=[step_register],
        else_steps=[],
    )

    pipeline = Pipeline(
        name=config.pipeline_name,
        parameters=[input_data, feature_source, athena_output_s3_uri, model_approval_status, min_f1],
        steps=[step_process, step_train, step_eval, step_condition],
        sagemaker_session=session,
    )
    pipeline.upsert(role_arn=config.sagemaker_execution_role_arn)
    update_state(pipeline_name=config.pipeline_name)
    LOGGER.info("Created or updated SageMaker Pipeline %s", config.pipeline_name)


if __name__ == "__main__":
    main()
