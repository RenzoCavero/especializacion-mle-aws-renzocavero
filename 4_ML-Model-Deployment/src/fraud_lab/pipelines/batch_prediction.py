from __future__ import annotations

import argparse
from typing import Any

from fraud_lab.common.io_utils import read_csv, write_csv
from fraud_lab.config import data_dir, ensure_fraud_dirs
from fraud_lab.feature_store.offline_store import LocalOfflineFeatureStore
from fraud_lab.feature_store.seed_feature_store import seed_feature_store
from fraud_lab.features.current_transaction_features import build_current_transaction_features
from fraud_lab.features.feature_contract import default_contract, load_feature_order
from fraud_lab.features.feature_vector import assemble_feature_vector
from fraud_lab.model.model_loader import load_model_endpoint


def _coerce_curated(row: dict[str, Any]) -> dict[str, Any]:
    coerced = dict(row)
    coerced["amount"] = float(coerced["amount"])
    coerced["amount_pen"] = float(coerced["amount_pen"])
    return coerced


def batch_prediction() -> dict[str, str]:
    ensure_fraud_dirs()
    curated_path = data_dir() / "lake" / "curated" / "transactions_to_score.csv"
    rows = [_coerce_curated(row) for row in read_csv(curated_path)]
    offline = LocalOfflineFeatureStore()
    if not offline.read_records("user_behavior_features"):
        seed_feature_store()
    endpoint = load_model_endpoint()
    contract = default_contract()
    feature_order = load_feature_order()
    predictions = []
    model_ready_rows = []

    for row in rows:
        current, warnings = build_current_transaction_features(row)
        offline_features = offline.get_many_for_transaction(row)
        vector = assemble_feature_vector(row, current, offline_features, contract, warnings)
        prediction = endpoint.predict(vector.values, request_id=f"batch-{row['transaction_id']}")
        predictions.append(
            {
                "transaction_id": row["transaction_id"],
                "fraud_score": prediction["fraud_score"],
                "decision": prediction["decision"],
                "model_version": prediction["model_version"],
                "feature_version": prediction["feature_version"],
            }
        )
        model_ready_rows.append({"transaction_id": row["transaction_id"], **vector.values})

    prediction_path = data_dir() / "batch" / "predictions" / "batch_predictions.csv"
    model_ready_path = data_dir() / "batch" / "model_ready" / "batch_model_ready.csv"
    write_csv(prediction_path, predictions)
    write_csv(model_ready_path, model_ready_rows, fieldnames=["transaction_id", *feature_order])
    print(f"Batch predictions: {prediction_path}")
    return {"predictions": str(prediction_path), "model_ready": str(model_ready_path)}


def main() -> None:
    argparse.ArgumentParser(description="Run local batch fraud scoring with Offline Store point-in-time joins.").parse_args()
    batch_prediction()


if __name__ == "__main__":
    main()
