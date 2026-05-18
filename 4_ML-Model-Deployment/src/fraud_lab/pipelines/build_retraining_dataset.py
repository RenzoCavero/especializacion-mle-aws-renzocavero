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


def _coerce_curated(row: dict[str, Any]) -> dict[str, Any]:
    coerced = dict(row)
    coerced["amount"] = float(coerced["amount"])
    coerced["amount_pen"] = float(coerced["amount_pen"])
    return coerced


def build_retraining_dataset() -> dict[str, str]:
    ensure_fraud_dirs()
    curated_rows = [_coerce_curated(row) for row in read_csv(data_dir() / "lake" / "curated" / "historical_transactions.csv")]
    labels = {row["transaction_id"]: row for row in read_csv(data_dir() / "lake" / "curated" / "fraud_labels.csv")}
    offline = LocalOfflineFeatureStore()
    if not offline.read_records("user_behavior_features"):
        seed_feature_store()
    contract = default_contract()
    feature_order = load_feature_order()
    dataset = []

    for row in curated_rows:
        label = labels.get(row["transaction_id"])
        if not label:
            continue
        current, warnings = build_current_transaction_features(row)
        offline_features = offline.get_many_for_transaction(row)
        vector = assemble_feature_vector(row, current, offline_features, contract, warnings)
        dataset.append(
            {
                "transaction_id": row["transaction_id"],
                "event_time": row["timestamp"],
                **vector.values,
                "label": int(label["label"]),
                "label_source": label["label_source"],
                "label_event_time": label["label_event_time"],
            }
        )

    output_path = data_dir() / "retraining" / "training_dataset.csv"
    write_csv(
        output_path,
        dataset,
        fieldnames=[
            "transaction_id",
            "event_time",
            *feature_order,
            "label",
            "label_source",
            "label_event_time",
        ],
    )
    print(f"Retraining dataset: {output_path}")
    return {"training_dataset": str(output_path)}


def main() -> None:
    argparse.ArgumentParser(description="Build supervised retraining dataset with point-in-time features.").parse_args()
    build_retraining_dataset()


if __name__ == "__main__":
    main()
