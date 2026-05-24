from __future__ import annotations

import pytest

from monitoring.parse_violations import parse_violations
from src.check_data_capture import parse_s3_uri
from src.config import load_config
from src.create_monitoring_schedule import model_monitor_image_uri, validate_monitoring_schedule_expression


def test_monitoring_contract_contains_baseline_paths(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    cfg = load_config(validate=True)
    assert cfg.statistics_s3_uri.endswith("/monitoring/baseline/statistics.json")
    assert cfg.constraints_s3_uri.endswith("/monitoring/baseline/constraints.json")
    assert "monitoring" in cfg.monitoring_s3_uri
    assert cfg.model_quality_predictions_s3_uri.endswith("/model-quality/predictions")
    assert cfg.model_quality_baseline_s3_uri.endswith("/model-quality/baseline")
    assert cfg.model_quality_constraints_s3_uri.endswith("/model-quality/baseline/constraints.json")
    assert cfg.model_quality_ground_truth_s3_uri.endswith("/model-quality/ground-truth")
    assert cfg.model_quality_reports_s3_uri.endswith("/model-quality/reports")
    assert cfg.model_quality_schedule_name == "mlops-model-quality-schedule"
    assert cfg.model_quality_problem_type == "BinaryClassification"
    assert cfg.model_quality_inference_attribute == "prediction"
    assert cfg.model_quality_probability_attribute == "probability"


def test_parse_violations_summary():
    payload = {
        "violations": [
            {"feature_name": "monthly_spend", "constraint_check_type": "data_type_check"},
            {"feature_name": "monthly_spend", "constraint_check_type": "baseline_drift_check"},
        ]
    }
    summary = parse_violations(payload)
    assert summary["violations_count"] == 2
    assert summary["severity"] == "medium"
    assert summary["by_feature"]["monthly_spend"] == 2


def test_parse_violations_marks_large_counts_as_critical():
    payload = {"violations": [{"feature_name": f"feature_{idx}"} for idx in range(10)]}
    summary = parse_violations(payload)
    assert summary["violations_count"] == 10
    assert summary["severity"] == "critical"


def test_parse_data_capture_s3_uri():
    bucket, prefix = parse_s3_uri("s3://example-bucket/mlops-lab/lab/data-capture/endpoint")
    assert bucket == "example-bucket"
    assert prefix == "mlops-lab/lab/data-capture/endpoint"


def test_model_monitor_image_uri_for_us_east_1(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    cfg = load_config(validate=True)
    assert model_monitor_image_uri(cfg) == (
        "156813124566.dkr.ecr.us-east-1.amazonaws.com/sagemaker-model-monitor-analyzer"
    )


def test_model_monitor_schedule_expression_validation():
    for expression in ["NOW", "cron(0 * ? * * *)", "cron(0 12 ? * * *)", "cron(0 0/2 ? * * *)"]:
        validate_monitoring_schedule_expression(expression)

    with pytest.raises(ValueError, match="minute 45"):
        validate_monitoring_schedule_expression("cron(45 * ? * * *)")

    with pytest.raises(ValueError, match="sub-hour"):
        validate_monitoring_schedule_expression("rate(45 minutes)")


def test_batch_monitoring_defaults(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    cfg = load_config(validate=True)
    assert cfg.batch_transform_input_s3_uri.endswith("/data/raw/inference_normal.jsonl")
    assert cfg.batch_transform_output_s3_uri.endswith("/batch-transform/output")
    assert cfg.batch_data_capture_s3_uri.endswith("/batch-transform/data-capture")
    assert cfg.batch_monitoring_schedule_name == "mlops-lab-batch-monitoring-schedule"
    assert cfg.custom_batch_data_quality_reports_s3_uri.endswith("/batch-transform/custom-monitoring/reports")
    assert cfg.batch_violations_metric_name == "BatchDataQualityViolations"
