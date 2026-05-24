from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("joblib")
pytest.importorskip("sklearn")
pd = pytest.importorskip("pandas")

from processing.evaluate import evaluate
from processing.preprocess import preprocess
from src.config import LabConfig
from src.generate_sample_data import generate
from training.train import train


def test_standalone_synthetic_model_passes_default_quality_gate(tmp_path: Path):
    config = LabConfig(local_cache_dir=tmp_path / "cache", local_outputs_dir=tmp_path / "outputs")
    generated = generate(config, seed=42, n_rows=1200)
    baseline_frame = pd.read_csv(generated["baseline"])
    assert "record_id" in baseline_frame.columns
    assert "churned" not in baseline_frame.columns

    train_path = tmp_path / "processing" / "train" / "train.csv"
    test_path = tmp_path / "processing" / "test" / "test.csv"
    baseline_path = tmp_path / "processing" / "baseline" / "baseline.csv"
    model_dir = tmp_path / "model"
    evaluation_path = tmp_path / "evaluation" / "evaluation.json"

    preprocess(generated["train"], train_path, test_path, baseline_path)
    model_path = train(train_path, model_dir, n_estimators=120)
    metrics = evaluate(model_path, test_path, evaluation_path)

    assert metrics["f1"] >= 0.70
    assert metrics["auc"] >= 0.70
