from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")

from src.capture_model_quality_data import _ground_truth_lookup, _resolve_label
from src.check_model_quality import _compute_metrics, _quality_status
from src.config import LabConfig
from src.create_custom_model_quality_schedule import _lambda_environment, _validate_eventbridge_schedule_expression
from src.create_model_quality_schedule import (
    _inline_schedule_request,
    _json_or_column_attribute,
    _model_quality_job_definition_request,
)
from src.custom_model_quality_job import custom_model_quality_processing_request
from src.generate_model_quality_baseline import _build_model_quality_artifacts, _model_quality_baseline_environment


def test_model_quality_metrics_join_contract_passes_default_thresholds():
    joined = pd.DataFrame(
        [
            {"inference_id": "a", "label": 1, "prediction": 1, "probability": 0.91},
            {"inference_id": "b", "label": 0, "prediction": 0, "probability": 0.08},
            {"inference_id": "c", "label": 1, "prediction": 1, "probability": 0.78},
            {"inference_id": "d", "label": 0, "prediction": 0, "probability": 0.22},
        ]
    )
    config = LabConfig(model_quality_min_records=4)

    metrics = _compute_metrics(joined)
    status = _quality_status(config, metrics)

    assert metrics["records_evaluated"] == 4
    assert metrics["accuracy"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["auc"] == 1.0
    assert status["status"] == "pass"


def test_model_quality_status_reports_insufficient_data_before_failing_quality():
    joined = pd.DataFrame(
        [
            {"inference_id": "a", "label": 1, "prediction": 0, "probability": 0.45},
            {"inference_id": "b", "label": 0, "prediction": 1, "probability": 0.55},
        ]
    )
    config = LabConfig(model_quality_min_records=20)

    metrics = _compute_metrics(joined)
    status = _quality_status(config, metrics)

    assert metrics["records_evaluated"] == 2
    assert status["status"] == "insufficient_data"


def test_model_quality_ground_truth_lookup_prefers_generated_jsonl(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "inference_drift_ground_truth.jsonl").write_text(
        '{"record_id": "drift-custom-00001", "churned": 1}\n'
        '{"record_id": "drift-custom-00002", "churned": 0}\n',
        encoding="utf-8",
    )
    config = LabConfig(local_cache_dir=cache_dir)

    labels = _ground_truth_lookup(config, "drift")

    assert labels == {"drift-custom-00001": 1, "drift-custom-00002": 0}


def test_model_quality_label_modes_can_force_alarm_scenario():
    assert _resolve_label(source_label=1, prediction=1, label_mode="source") == 1
    assert _resolve_label(source_label=1, prediction=1, label_mode="invert-source") == 0
    assert _resolve_label(source_label=1, prediction=1, label_mode="opposite-prediction") == 0
    assert _resolve_label(source_label=0, prediction=0, label_mode="opposite-prediction") == 1


def test_native_model_quality_job_definition_contract():
    config = LabConfig(
        s3_bucket_name="example-bucket",
        sagemaker_execution_role_arn="arn:aws:iam::123456789012:role/example",
    )

    request = _model_quality_job_definition_request(
        config=config,
        image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/sagemaker-model-monitor-analyzer",
        instance_type="ml.m6i.large",
    )

    assert request["ModelQualityAppSpecification"]["ProblemType"] == "BinaryClassification"
    assert request["ModelQualityAppSpecification"]["Environment"]["publish_cloudwatch_metrics"] == "Enabled"
    assert request["ModelQualityBaselineConfig"]["ConstraintsResource"]["S3Uri"].endswith(
        "/model-quality/baseline/constraints.json"
    )
    assert request["ModelQualityJobInput"]["GroundTruthS3Input"]["S3Uri"].endswith("/model-quality/ground-truth")
    endpoint_input = request["ModelQualityJobInput"]["EndpointInput"]
    assert endpoint_input["EndpointName"] == "mlops-lab-endpoint"
    assert endpoint_input["InferenceAttribute"] == "$.prediction"
    assert endpoint_input["ProbabilityAttribute"] == "$.probability"
    assert "ProbabilityThresholdAttribute" not in endpoint_input


def test_model_quality_baseline_artifacts_use_binary_classification_schema():
    joined = pd.DataFrame(
        [
            {"label": 1, "prediction": 1, "probability": 0.91},
            {"label": 0, "prediction": 0, "probability": 0.08},
            {"label": 1, "prediction": 1, "probability": 0.78},
            {"label": 0, "prediction": 0, "probability": 0.22},
        ]
    )
    statistics, constraints = _build_model_quality_artifacts(joined, LabConfig())

    assert "binary_classification_metrics" in statistics
    assert "confusion_matrix" in statistics["binary_classification_metrics"]
    assert statistics["binary_classification_metrics"]["f1"]["value"] == 1.0
    assert statistics["binary_classification_metrics"]["f1"]["standard_deviation"] == "NaN"
    assert "binary_classification_constraints" in constraints
    assert constraints["binary_classification_constraints"]["f1"]["comparison_operator"] == "LessThanThreshold"


def test_model_quality_baseline_environment_omits_probability_threshold():
    environment = _model_quality_baseline_environment(LabConfig())

    assert environment["analysis_type"] == "MODEL_QUALITY"
    assert environment["problem_type"] == "BinaryClassification"
    assert environment["inference_attribute"] == "prediction"
    assert environment["probability_attribute"] == "probability"
    assert environment["ground_truth_attribute"] == "label"
    assert "probability_threshold_attribute" not in environment


def test_model_quality_endpoint_attributes_use_jsonpath_for_named_json_fields():
    assert _json_or_column_attribute("prediction") == "$.prediction"
    assert _json_or_column_attribute("$.prediction") == "$.prediction"
    assert _json_or_column_attribute("0") == "0"


def test_inline_model_quality_schedule_contract():
    config = LabConfig(
        s3_bucket_name="example-bucket",
        sagemaker_execution_role_arn="arn:aws:iam::123456789012:role/example",
    )

    request = _inline_schedule_request(
        config=config,
        image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/sagemaker-model-monitor-analyzer",
        instance_type="ml.m6i.large",
        baseline_metadata={"baseline_job_name": "baseline-job"},
        schedule_name="mlops-model-quality-schedule",
    )

    schedule_config = request["MonitoringScheduleConfig"]
    assert request["MonitoringScheduleName"] == "mlops-model-quality-schedule"
    assert schedule_config["MonitoringType"] == "ModelQuality"
    definition = schedule_config["MonitoringJobDefinition"]
    assert definition["BaselineConfig"]["BaseliningJobName"] == "baseline-job"
    assert definition["BaselineConfig"]["ConstraintsResource"]["S3Uri"].endswith(
        "/model-quality/baseline/constraints.json"
    )
    assert definition["Environment"]["ground_truth_input"].endswith("/model-quality/ground-truth")
    endpoint_input = definition["MonitoringInputs"][0]["EndpointInput"]
    assert endpoint_input["EndpointName"] == "mlops-lab-endpoint"
    assert endpoint_input["InferenceAttribute"] == "$.prediction"
    assert endpoint_input["ProbabilityAttribute"] == "$.probability"
    assert "ProbabilityThresholdAttribute" not in endpoint_input


def test_custom_model_quality_processing_request_contract():
    config = LabConfig(
        s3_bucket_name="example-bucket",
        sagemaker_execution_role_arn="arn:aws:iam::123456789012:role/example",
    )

    request = custom_model_quality_processing_request(
        config=config,
        job_name="custom-model-quality-job",
        image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3",
        instance_type="ml.m6i.large",
        code_s3_uri="s3://example-bucket/mlops-lab/lab/model-quality/custom/code",
    )

    assert request["ProcessingJobName"] == "custom-model-quality-job"
    assert request["AppSpecification"]["ContainerEntrypoint"] == [
        "python3",
        "/opt/ml/processing/code/custom_model_quality.py",
    ]
    assert request["Environment"]["PREDICTIONS_S3_URI"].endswith("/model-quality/predictions")
    assert request["Environment"]["GROUND_TRUTH_DEBUG_S3_URI"].endswith("/model-quality/ground-truth-debug")
    assert request["Environment"]["MODEL_QUALITY_F1_METRIC_NAME"] == "ModelQualityF1"
    assert request["ProcessingInputs"][0]["S3Input"]["S3Uri"].endswith("/model-quality/custom/code")
    assert request["ProcessingOutputConfig"]["Outputs"][0]["S3Output"]["S3Uri"].endswith(
        "/model-quality/custom/reports"
    )


def test_custom_model_quality_processing_request_can_scope_to_explicit_objects():
    config = LabConfig(
        s3_bucket_name="example-bucket",
        sagemaker_execution_role_arn="arn:aws:iam::123456789012:role/example",
    )

    request = custom_model_quality_processing_request(
        config=config,
        job_name="custom-model-quality-job",
        image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3",
        instance_type="ml.m6i.large",
        code_s3_uri="s3://example-bucket/mlops-lab/lab/model-quality/custom/code",
        predictions_s3_uri="s3://example-bucket/mlops-lab/lab/model-quality/predictions/run/predictions.jsonl",
        ground_truth_debug_s3_uri=(
            "s3://example-bucket/mlops-lab/lab/model-quality/ground-truth-debug/run/ground_truth_debug.jsonl"
        ),
        window_hours=1,
    )

    assert request["Environment"]["PREDICTIONS_S3_URI"].endswith("/predictions/run/predictions.jsonl")
    assert request["Environment"]["GROUND_TRUTH_DEBUG_S3_URI"].endswith(
        "/ground-truth-debug/run/ground_truth_debug.jsonl"
    )
    assert request["Environment"]["CUSTOM_MODEL_QUALITY_WINDOW_HOURS"] == "1"


def test_custom_model_quality_lambda_environment_omits_reserved_aws_region():
    config = LabConfig(
        s3_bucket_name="example-bucket",
        sagemaker_execution_role_arn="arn:aws:iam::123456789012:role/sagemaker",
    )

    environment = _lambda_environment(
        config,
        image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3",
        instance_type="ml.m6i.large",
        code_s3_uri="s3://example-bucket/mlops-lab/lab/model-quality/custom/code",
    )

    assert "AWS_REGION" not in environment
    assert environment["SAGEMAKER_EXECUTION_ROLE_ARN"] == "arn:aws:iam::123456789012:role/sagemaker"
    assert environment["PROCESSING_INSTANCE_TYPE"] == "ml.m6i.large"


def test_custom_model_quality_schedule_rejects_now_because_manual_runner_exists():
    with pytest.raises(ValueError, match="start_custom_model_quality_job"):
        _validate_eventbridge_schedule_expression("NOW")

    _validate_eventbridge_schedule_expression("cron(0 * ? * * *)")
