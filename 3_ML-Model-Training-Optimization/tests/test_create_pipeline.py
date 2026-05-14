from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_create_pipeline_uses_pipeline_session_not_runtime_session() -> None:
    source = (PROJECT_ROOT / "src" / "create_pipeline.py").read_text(encoding="utf-8")

    assert "from src.aws_clients import pipeline_session" in source
    assert "session = pipeline_session(config)" in source
    assert "sagemaker_session(config)" not in source


def test_aws_clients_exposes_pipeline_session() -> None:
    source = (PROJECT_ROOT / "src" / "aws_clients.py").read_text(encoding="utf-8")

    assert "def pipeline_session" in source
    assert "PipelineSession" in source
