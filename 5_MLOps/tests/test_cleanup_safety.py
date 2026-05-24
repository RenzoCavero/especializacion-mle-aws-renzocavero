from __future__ import annotations

from src import cleanup_all as cleanup_all_module
from src import cleanup_sagemaker_resources
from src.cleanup_endpoint import cleanup_endpoint
from src.cleanup_s3_artifacts import _lab_prefix
from src.config import LabConfig
from src.trigger_retraining import trigger_retraining


def test_cleanup_skips_external_endpoint_by_default(monkeypatch):
    monkeypatch.setenv("LAB_MODE", "integrated")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    monkeypatch.setenv("ENDPOINT_NAME", "external-endpoint")
    result = cleanup_endpoint(include_external=False)
    assert result["skipped"] is True
    assert "protects external" in result["reason"]


def test_automatic_retraining_false_skips_execution(monkeypatch):
    monkeypatch.setenv("LAB_MODE", "standalone")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    monkeypatch.setenv("ENABLE_AUTOMATIC_RETRAINING", "false")
    result = trigger_retraining()
    assert result["status"] == "skipped"
    assert result["reason"] == "ENABLE_AUTOMATIC_RETRAINING=false"


def test_s3_cleanup_allows_only_exact_lab_prefix():
    config = LabConfig(
        aws_region="us-east-1",
        s3_bucket_name="example-bucket",
        resource_prefix="mlops-lab",
        environment="lab",
    )
    assert _lab_prefix(config) == ("example-bucket", "mlops-lab/lab/")


def test_s3_cleanup_rejects_broad_prefix():
    config = LabConfig(
        aws_region="us-east-1",
        s3_bucket_name="example-bucket",
        resource_prefix="mlops-lab",
        environment="",
    )
    try:
        _lab_prefix(config)
    except ValueError as exc:
        assert "unexpected S3 prefix" in str(exc) or "broad S3 prefix" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected broad prefix to be rejected")


def test_cleanup_all_deletes_s3_by_default(monkeypatch):
    config = LabConfig(aws_region="us-east-1", s3_bucket_name="example-bucket")
    calls: dict[str, object] = {}

    def fake_cleanup_s3_artifacts(execute=True):
        calls["s3_execute"] = execute
        return {"s3": True}

    monkeypatch.setattr(cleanup_all_module, "load_config", lambda validate=True: config)
    monkeypatch.setattr(cleanup_all_module, "cleanup_endpoint", lambda include_external=False: {"endpoint": True})
    monkeypatch.setattr(cleanup_all_module, "cleanup_monitoring", lambda delete_s3_outputs=True: {"delete_s3_outputs": delete_s3_outputs})
    monkeypatch.setattr(cleanup_all_module, "cleanup_feedback_loop", lambda: {"feedback": True})
    monkeypatch.setattr(cleanup_all_module, "cleanup_sagemaker_resources", lambda include_external=False: {"sagemaker": True})
    monkeypatch.setattr(cleanup_all_module, "cleanup_s3_artifacts", fake_cleanup_s3_artifacts)
    monkeypatch.setattr(cleanup_all_module, "cleanup_local_outputs", lambda execute=False: {"local_execute": execute})
    monkeypatch.setattr(cleanup_all_module, "write_metadata", lambda config, name, payload: None)

    result = cleanup_all_module.cleanup_all()

    assert result["s3_outputs_deleted"] is True
    assert calls["s3_execute"] is True


def test_cleanup_sagemaker_extracts_job_names_from_metadata(monkeypatch):
    config = LabConfig(aws_region="us-east-1", s3_bucket_name="example-bucket")
    metadata = {
        "baseline": {"baseline_job_name": "baseline-job"},
        "custom_model_quality_job": {
            "job_name": "custom-mq",
            "processing_job_description": {"ProcessingJobName": "custom-mq-described"},
        },
        "batch_transform": {
            "transform_job_name": "batch-transform",
            "description": {"TransformJobName": "batch-transform-described"},
        },
        "pipeline_execution_status": {
            "steps": [
                {
                    "Metadata": {
                        "ProcessingJob": {"Arn": "arn:aws:sagemaker:us-east-1:123:processing-job/pipeline-process"},
                        "TrainingJob": {"Arn": "arn:aws:sagemaker:us-east-1:123:training-job/pipeline-train"},
                    }
                }
            ]
        },
    }

    monkeypatch.setattr(cleanup_sagemaker_resources, "read_metadata", lambda cfg, name: metadata.get(name, {}))

    result = cleanup_sagemaker_resources._job_names_from_metadata(config)

    assert result["processing"] == ["baseline-job", "custom-mq", "custom-mq-described", "pipeline-process"]
    assert result["training"] == ["pipeline-train"]
    assert result["transform"] == ["batch-transform", "batch-transform-described"]
