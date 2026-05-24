from __future__ import annotations

import pytest

from src.config import LabConfig
from src.create_custom_batch_data_quality_schedule import _lambda_environment as _batch_lambda_environment
from src.create_custom_data_quality_schedule import _lambda_environment, _validate_eventbridge_schedule_expression
from src.custom_data_quality_job import custom_data_quality_processing_request


def test_custom_data_quality_processing_request_contract():
    config = LabConfig(
        s3_bucket_name="example-bucket",
        sagemaker_execution_role_arn="arn:aws:iam::123456789012:role/example",
    )

    request = custom_data_quality_processing_request(
        config=config,
        job_name="custom-data-quality-job",
        image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3",
        instance_type="ml.m6i.large",
        code_s3_uri="s3://example-bucket/mlops-lab/lab/monitoring/custom/code",
        current_data_s3_uri="s3://example-bucket/mlops-lab/lab/data/raw/inference_drift.jsonl",
        window_hours=1,
    )

    assert request["ProcessingJobName"] == "custom-data-quality-job"
    assert request["AppSpecification"]["ContainerEntrypoint"] == [
        "python3",
        "/opt/ml/processing/code/custom_data_quality.py",
    ]
    assert request["Environment"]["BASELINE_DATA_S3_URI"].endswith("/data/raw/baseline_monitor.csv")
    assert request["Environment"]["CURRENT_DATA_S3_URI"].endswith("/data/raw/inference_drift.jsonl")
    assert request["Environment"]["DATA_CAPTURE_S3_URI"].endswith("/data-capture/mlops-lab-endpoint")
    assert request["Environment"]["VIOLATIONS_METRIC_NAME"] == "DataQualityViolations"
    assert request["Environment"]["CUSTOM_DATA_QUALITY_WINDOW_HOURS"] == "1"
    assert request["ProcessingInputs"][0]["S3Input"]["S3Uri"].endswith("/monitoring/custom/code")
    assert request["ProcessingOutputConfig"]["Outputs"][0]["S3Output"]["S3Uri"].endswith(
        "/monitoring/custom/reports"
    )


def test_custom_data_quality_lambda_environment_omits_reserved_aws_region():
    config = LabConfig(
        s3_bucket_name="example-bucket",
        sagemaker_execution_role_arn="arn:aws:iam::123456789012:role/sagemaker",
    )

    environment = _lambda_environment(
        config,
        image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3",
        instance_type="ml.m6i.large",
        code_s3_uri="s3://example-bucket/mlops-lab/lab/monitoring/custom/code",
    )

    assert "AWS_REGION" not in environment
    assert environment["SAGEMAKER_EXECUTION_ROLE_ARN"] == "arn:aws:iam::123456789012:role/sagemaker"
    assert environment["PROCESSING_INSTANCE_TYPE"] == "ml.m6i.large"
    assert environment["BASELINE_DATA_S3_URI"].endswith("/data/raw/baseline_monitor.csv")


def test_custom_data_quality_processing_request_supports_batch_metric_contract():
    config = LabConfig(
        s3_bucket_name="example-bucket",
        sagemaker_execution_role_arn="arn:aws:iam::123456789012:role/example",
    )

    request = custom_data_quality_processing_request(
        config=config,
        job_name="custom-batch-data-quality-job",
        image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3",
        instance_type="ml.m6i.large",
        code_s3_uri="s3://example-bucket/mlops-lab/lab/batch-transform/custom-monitoring/code",
        current_data_s3_uri="s3://example-bucket/mlops-lab/lab/data/raw/inference_normal.jsonl",
        reports_s3_uri="s3://example-bucket/mlops-lab/lab/batch-transform/custom-monitoring/reports",
        metric_name="BatchDataQualityViolations",
        metric_dimension_name="BatchMonitoringSchedule",
        metric_dimension_value="mlops-lab-batch-monitoring-schedule",
        endpoint_name="mlops-lab-lab-batch-model",
    )

    assert request["Environment"]["VIOLATIONS_METRIC_NAME"] == "BatchDataQualityViolations"
    assert request["Environment"]["METRIC_DIMENSION_NAME"] == "BatchMonitoringSchedule"
    assert request["Environment"]["METRIC_DIMENSION_VALUE"] == "mlops-lab-batch-monitoring-schedule"
    assert request["Environment"]["ENDPOINT_NAME"] == "mlops-lab-lab-batch-model"
    assert request["ProcessingOutputConfig"]["Outputs"][0]["S3Output"]["S3Uri"].endswith(
        "/batch-transform/custom-monitoring/reports"
    )


def test_custom_batch_data_quality_lambda_environment_uses_batch_inputs():
    config = LabConfig(
        s3_bucket_name="example-bucket",
        sagemaker_execution_role_arn="arn:aws:iam::123456789012:role/sagemaker",
    )

    environment = _batch_lambda_environment(
        config,
        image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3",
        instance_type="ml.m6i.large",
        code_s3_uri="s3://example-bucket/mlops-lab/lab/batch-transform/custom-monitoring/code",
    )

    assert "AWS_REGION" not in environment
    assert environment["CURRENT_DATA_S3_URI"].endswith("/data/raw/inference_normal.jsonl")
    assert environment["DATA_CAPTURE_S3_URI"].endswith("/batch-transform/data-capture")
    assert environment["VIOLATIONS_METRIC_NAME"] == "BatchDataQualityViolations"
    assert environment["METRIC_DIMENSION_NAME"] == "BatchMonitoringSchedule"


def test_custom_data_quality_schedule_rejects_now_because_manual_runner_exists():
    with pytest.raises(ValueError, match="start_custom_data_quality_job"):
        _validate_eventbridge_schedule_expression("NOW")

    _validate_eventbridge_schedule_expression("cron(0 * ? * * *)")
