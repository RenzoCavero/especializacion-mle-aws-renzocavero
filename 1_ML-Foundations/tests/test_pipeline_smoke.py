from pathlib import Path

import pandas as pd

from src.batch_inference import run_batch_inference
from src.data_preparation import prepare_data
from src.evaluate import evaluate_model
from src.generate_dataset import generate_dataset
from src.model_card import generate_model_card
from src.monitor import run_monitoring
from src.train import train_model


def test_local_pipeline_smoke(project_tmp_path: Path) -> None:
    raw_path = project_tmp_path / "data" / "raw" / "transactions.csv"
    raw_batch_path = project_tmp_path / "data" / "raw" / "batch.csv"
    train_path = project_tmp_path / "data" / "processed" / "train.csv"
    test_path = project_tmp_path / "data" / "processed" / "test.csv"
    batch_path = project_tmp_path / "data" / "processed" / "batch_input.csv"
    model_path = project_tmp_path / "artifacts" / "model" / "model.joblib"
    metadata_path = project_tmp_path / "artifacts" / "model" / "model_metadata.json"
    training_metrics_path = project_tmp_path / "artifacts" / "metrics" / "training_metrics.json"
    eval_metrics_path = project_tmp_path / "artifacts" / "metrics" / "evaluation_metrics.json"
    eval_report_path = project_tmp_path / "artifacts" / "metrics" / "evaluation_report.md"
    predictions_path = project_tmp_path / "artifacts" / "predictions" / "batch_predictions.csv"
    summary_path = project_tmp_path / "artifacts" / "predictions" / "batch_summary.json"
    monitor_path = project_tmp_path / "artifacts" / "metrics" / "monitoring_report.json"
    monitor_md_path = project_tmp_path / "artifacts" / "metrics" / "monitoring_report.md"
    monitor_charts_dir = project_tmp_path / "artifacts" / "metrics" / "drift_charts"
    model_card_path = project_tmp_path / "artifacts" / "governance" / "model_card.md"
    data_profile_path = project_tmp_path / "data" / "processed" / "data_profile.json"
    feature_schema_path = project_tmp_path / "data" / "processed" / "feature_schema.json"

    generate_dataset(raw_path, raw_batch_path, n_rows=800, batch_rows=80, seed=321)
    prepare_data(raw_path, raw_batch_path, train_path, test_path, batch_path, data_profile_path, feature_schema_path, seed=321)
    train_model(train_path, model_path, training_metrics_path, metadata_path)
    evaluation = evaluate_model(test_path, model_path, eval_metrics_path, eval_report_path)
    run_batch_inference(batch_path, model_path, predictions_path, summary_path)
    monitoring = run_monitoring(train_path, batch_path, predictions_path, monitor_path, monitor_md_path, monitor_charts_dir)
    card = generate_model_card(metadata_path, eval_metrics_path, data_profile_path, monitor_path, model_card_path)

    predictions = pd.read_csv(predictions_path)
    assert model_path.exists()
    assert eval_metrics_path.exists()
    assert predictions_path.exists()
    assert model_card_path.exists()
    assert "transaction_id" in predictions.columns
    assert "fraud_probability" in predictions.columns
    assert "risk_decision" in predictions.columns
    assert evaluation["metrics"]["recall"] is not None
    assert monitoring["current_rows"] == 80
    assert (monitor_charts_dir / "psi_by_feature.svg").exists()
    assert (monitor_charts_dir / "alert_heatmap.svg").exists()
    assert card["approval_status"] == "local-demo-not-approved-for-production"
