from fraud_lab.common.io_utils import read_csv
from fraud_lab.pipelines.batch_prediction import batch_prediction
from fraud_lab.pipelines.cleaned_to_curated import cleaned_to_curated
from fraud_lab.pipelines.generate_synthetic_data import generate_synthetic_data
from fraud_lab.pipelines.raw_to_cleaned import raw_to_cleaned


def test_batch_prediction_uses_offline_store(monkeypatch, tmp_path):
    monkeypatch.setenv("FRAUD_LAB_ROOT", str(tmp_path))
    generate_synthetic_data()
    raw_to_cleaned()
    cleaned_to_curated()

    outputs = batch_prediction()
    rows = read_csv(tmp_path / "data" / "batch" / "predictions" / "batch_predictions.csv")

    assert outputs["predictions"].endswith("batch_predictions.csv")
    assert len(rows) == 3
    assert {"transaction_id", "fraud_score", "decision"}.issubset(rows[0])

