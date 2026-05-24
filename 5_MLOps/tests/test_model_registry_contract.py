from __future__ import annotations

from src.config import load_config
from src.register_model_metadata import extract_evaluation_metrics, metadata_from_metrics
from pipelines.build.pipeline_definition import build_pipeline_contract


def test_registry_contract_includes_approval_status(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    cfg = load_config(validate=True)
    registry = build_pipeline_contract(cfg)["registry"]
    assert registry["model_package_group_name"] == "mlops-model-package-group"
    assert registry["initial_approval_status"] == "PendingManualApproval"


def test_registry_metadata_formats_visible_metrics(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    cfg = load_config(validate=True)
    metrics = extract_evaluation_metrics(
        {
            "binary_classification_metrics": {
                "accuracy": {"value": 0.91},
                "f1": {"value": 0.82},
                "auc": {"value": 0.94},
            }
        }
    )
    metadata = metadata_from_metrics(cfg, metrics, "s3://example-bucket/evaluation/evaluation.json")
    assert metadata["metric_accuracy"] == "0.910000"
    assert metadata["metric_f1"] == "0.820000"
    assert metadata["metric_auc"] == "0.940000"
    assert metadata["quality_gate_f1_threshold"] == "0.700000"
    assert metadata["evaluation_s3_uri"] == "s3://example-bucket/evaluation/evaluation.json"
