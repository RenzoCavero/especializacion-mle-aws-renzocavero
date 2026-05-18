from fraud_lab.common.io_utils import read_csv
from fraud_lab.pipelines.build_retraining_dataset import build_retraining_dataset
from fraud_lab.pipelines.cleaned_to_curated import cleaned_to_curated
from fraud_lab.pipelines.generate_synthetic_data import generate_synthetic_data
from fraud_lab.pipelines.raw_to_cleaned import raw_to_cleaned


def test_retraining_dataset_contains_labels_and_point_in_time_features(monkeypatch, tmp_path):
    monkeypatch.setenv("FRAUD_LAB_ROOT", str(tmp_path))
    generate_synthetic_data()
    raw_to_cleaned()
    cleaned_to_curated()

    build_retraining_dataset()
    rows = read_csv(tmp_path / "data" / "retraining" / "training_dataset.csv")
    t001 = next(row for row in rows if row["transaction_id"] == "T001")

    assert t001["label"] == "1"
    assert t001["merchant_risk_score"]
    assert float(t001["user_txn_count_1h"]) == 4.0

