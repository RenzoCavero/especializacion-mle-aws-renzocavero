import pytest

from src.aws_clients import get_sklearn_image_uri
from src.config import ConfigError, LabConfig, normalize_lab_mode


def test_lab_mode_accepts_expected_values():
    assert normalize_lab_mode("standalone") == "standalone"
    assert normalize_lab_mode("integrated") == "integrated"
    assert normalize_lab_mode("standalone_mode") == "standalone"


def test_lab_mode_rejects_invalid_value():
    with pytest.raises(ConfigError):
        normalize_lab_mode("local")


def test_minimal_standalone_config(monkeypatch):
    monkeypatch.setenv("LAB_MODE", "standalone")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    monkeypatch.setenv("SAGEMAKER_EXECUTION_ROLE_ARN", "arn:aws:iam::123456789012:role/example")
    config = LabConfig.from_env(require_aws=True)
    assert config.lab_mode == "standalone"
    assert config.batch_instance_count == 1
    assert config.endpoint_name == "ml-deploy-realtime-endpoint"
    assert config.create_standalone_feature_group is True
    assert config.feature_group_name == "ml-deploy-lab-features"


def test_integrated_requires_model_reference(monkeypatch):
    monkeypatch.setenv("LAB_MODE", "integrated")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    monkeypatch.setenv("SAGEMAKER_EXECUTION_ROLE_ARN", "arn:aws:iam::123456789012:role/example")
    monkeypatch.delenv("MODEL_PACKAGE_ARN", raising=False)
    monkeypatch.delenv("MODEL_PACKAGE_GROUP_NAME", raising=False)
    monkeypatch.delenv("MODEL_ARTIFACT_S3_URI", raising=False)
    with pytest.raises(ConfigError):
        LabConfig.from_env(require_aws=True)


def test_sklearn_image_uri_falls_back_without_sdk(monkeypatch):
    config = LabConfig.from_env(require_aws=False)
    config.aws_region = "us-east-1"
    config.instance_type = "ml.m5.large"
    config.inference_image_uri = ""
    monkeypatch.setattr("src.aws_clients._retrieve_sklearn_image_with_sdk", lambda _: None)

    image_uri = get_sklearn_image_uri(config)

    assert image_uri == (
        "683313688378.dkr.ecr.us-east-1.amazonaws.com/"
        "sagemaker-scikit-learn:1.2-1-cpu-py3"
    )
