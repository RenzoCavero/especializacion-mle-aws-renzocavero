from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_create_pipeline_uses_pipeline_session_not_runtime_session() -> None:
    source = (PROJECT_ROOT / "src" / "create_pipeline.py").read_text(encoding="utf-8")

    assert "from src.aws_clients import pipeline_session" in source
    assert "session = pipeline_session(config)" in source
    assert "sagemaker_session(config)" not in source
    assert "IngestCuratedFeatures" in source
    assert "CuratedFeaturesS3Uri" in source


def test_create_hpo_pipeline_uses_managed_tuning_step() -> None:
    source = (PROJECT_ROOT / "src" / "create_hpo_pipeline.py").read_text(encoding="utf-8")

    assert "from sagemaker.workflow.steps import ProcessingStep, TuningStep" in source
    assert "HyperparameterTuner" in source
    assert "TuneChurnModel" in source
    assert "get_top_model_s3_uri" in source
    assert 'prefix="output/pipeline-hpo",' in source
    assert "output/pipeline-hpo/best-model" not in source
    assert "EvaluateBestHPOModel" in source
    assert "RegisterBestHPOModel" in source


def test_aws_clients_exposes_pipeline_session() -> None:
    source = (PROJECT_ROOT / "src" / "aws_clients.py").read_text(encoding="utf-8")

    assert "def pipeline_session" in source
    assert "PipelineSession" in source


def test_hpo_pipeline_permissions_include_listing_child_jobs() -> None:
    template = (PROJECT_ROOT / "infra" / "cloudformation" / "template.yaml").read_text(encoding="utf-8")

    assert "sagemaker:ListTrainingJobsForHyperParameterTuningJob" in template
