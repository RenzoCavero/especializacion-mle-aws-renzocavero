from __future__ import annotations

import pytest

from src.config import ConfigError, LabConfig, load_config


def test_minimal_standalone_config(monkeypatch):
    monkeypatch.setenv("LAB_MODE", "standalone")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    cfg = load_config(validate=True)
    assert cfg.is_standalone
    assert cfg.s3_base_uri == "s3://example-bucket/mlops-lab/lab"
    assert cfg.data_capture_s3_uri.endswith("/data-capture/mlops-lab-endpoint")
    assert cfg.auto_select_compute
    assert "ml.t3.medium" in cfg.processing_instance_type_candidates_list
    assert "ml.c6i.xlarge" in cfg.processing_instance_type_candidates_list
    assert cfg.model_monitor_processing_instance_type_candidates_list[0] == "ml.m6i.large"
    assert "ml.t3.medium" in cfg.model_monitor_processing_instance_type_candidates_list
    assert "ml.t3.medium" not in cfg.training_instance_type_candidates_list
    assert "ml.c6i.large" in cfg.batch_transform_instance_type_candidates_list
    assert cfg.metric_namespace == "MLOps/Lab"
    assert cfg.violations_metric_name == "DataQualityViolations"
    assert cfg.batch_violations_metric_name == "BatchDataQualityViolations"
    assert cfg.alarm_name == "mlops-data-quality-alarm"
    assert cfg.custom_data_quality_alarm_name == "mlops-custom-data-quality-alarm"
    assert cfg.custom_batch_data_quality_alarm_name == "mlops-custom-batch-data-quality-alarm"
    assert cfg.alarm_threshold == 1.0
    assert cfg.alarm_period_seconds == 300
    assert cfg.capture_endpoint_output is True
    assert cfg.model_quality_s3_uri.endswith("/model-quality")
    assert cfg.model_quality_predictions_s3_uri.endswith("/model-quality/predictions")
    assert cfg.model_quality_baseline_dataset_s3_uri.endswith("/model-quality/baseline/baseline.csv")
    assert cfg.model_quality_constraints_s3_uri.endswith("/model-quality/baseline/constraints.json")
    assert cfg.model_quality_ground_truth_s3_uri.endswith("/model-quality/ground-truth")
    assert cfg.model_quality_ground_truth_debug_s3_uri.endswith("/model-quality/ground-truth-debug")
    assert cfg.model_quality_reports_s3_uri.endswith("/model-quality/reports")
    assert cfg.model_quality_schedule_name == "mlops-model-quality-schedule"
    assert cfg.model_quality_job_definition_name == "mlops-model-quality-job-def"
    assert cfg.model_quality_metric_namespace == "aws/sagemaker/Endpoints/model-metrics"
    assert cfg.model_quality_native_metric_name == "f1"
    assert cfg.model_quality_alarm_name == "mlops-model-quality-alarm"
    assert cfg.custom_model_quality_alarm_name == "mlops-custom-model-quality-alarm"
    assert cfg.custom_model_quality_schedule_name == "mlops-custom-model-quality-schedule"
    assert cfg.custom_model_quality_trigger_lambda_name == "mlops-custom-model-quality-trigger"
    assert cfg.model_quality_f1_metric_name == "ModelQualityF1"
    assert cfg.model_quality_min_records == 20
    assert cfg.custom_model_quality_reports_s3_uri.endswith("/model-quality/custom/reports")
    assert cfg.custom_model_quality_code_s3_uri.endswith("/model-quality/custom/code")
    assert cfg.custom_model_quality_cron_expression == "cron(0 * ? * * *)"
    assert cfg.custom_data_quality_schedule_name == "mlops-custom-data-quality-schedule"
    assert cfg.custom_data_quality_trigger_lambda_name == "mlops-custom-data-quality-trigger"
    assert cfg.custom_batch_data_quality_schedule_name == "mlops-custom-batch-data-quality-schedule"
    assert cfg.custom_batch_data_quality_trigger_lambda_name == "mlops-custom-batch-data-quality-trigger"
    assert cfg.baseline_monitor_s3_uri.endswith("/data/raw/baseline_monitor.csv")
    assert cfg.custom_data_quality_reports_s3_uri.endswith("/monitoring/custom/reports")
    assert cfg.custom_data_quality_code_s3_uri.endswith("/monitoring/custom/code")
    assert cfg.custom_batch_data_quality_reports_s3_uri.endswith("/batch-transform/custom-monitoring/reports")
    assert cfg.custom_batch_data_quality_code_s3_uri.endswith("/batch-transform/custom-monitoring/code")
    assert cfg.custom_data_quality_cron_expression == "cron(0 * ? * * *)"
    assert cfg.custom_batch_data_quality_cron_expression == "cron(0 * ? * * *)"
    assert cfg.alarm_sns_topic_name == "mlops-lab-alarm-notifications"
    assert cfg.alarm_email == "enriquemejiagamarra@gmail.com"


def test_output_capture_can_be_disabled_explicitly(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    monkeypatch.setenv("CAPTURE_ENDPOINT_OUTPUT", "false")
    cfg = load_config(validate=True)
    assert cfg.capture_endpoint_output is False


def test_lab_mode_validation(monkeypatch):
    monkeypatch.setenv("LAB_MODE", "wrong")
    with pytest.raises(ConfigError):
        load_config(validate=False)


def test_integrated_mode_tracks_external_resources(monkeypatch):
    monkeypatch.setenv("LAB_MODE", "integrated")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    monkeypatch.setenv("ENDPOINT_NAME", "existing-endpoint")
    cfg = load_config(validate=True)
    assert cfg.is_integrated
    assert "existing-endpoint" in cfg.external_resource_names()


def test_missing_bucket_does_not_build_malformed_s3_uri():
    cfg = LabConfig(aws_region="us-east-1", s3_bucket_name="")
    assert cfg.s3_base_uri == ""
    assert cfg.data_capture_s3_uri == ""
    assert cfg.monitoring_s3_uri == ""
    assert cfg.model_quality_s3_uri == ""
