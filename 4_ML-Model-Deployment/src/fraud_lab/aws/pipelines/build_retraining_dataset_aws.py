from __future__ import annotations

import argparse
import json
from typing import Any

from fraud_lab.aws.feature_store import AwsFeatureStore
from fraud_lab.aws.s3_data_lake import S3DataLake
from fraud_lab.features.current_transaction_features import build_current_transaction_features
from fraud_lab.features.feature_contract import default_contract, load_feature_order
from fraud_lab.features.feature_vector import assemble_feature_vector


def _coerce_curated(row: dict[str, Any]) -> dict[str, Any]:
    coerced = dict(row)
    coerced["amount"] = float(coerced["amount"])
    coerced["amount_pen"] = float(coerced["amount_pen"])
    return coerced


def build_retraining_dataset_aws() -> dict[str, str]:
    feature_store = AwsFeatureStore()
    s3_lake = S3DataLake(feature_store.config, feature_store.clients)
    historical_rows = [
        _coerce_curated(row)
        for row in s3_lake.read_csv("lake", "curated", "historical_transactions.csv")
    ]
    labels = {
        row["transaction_id"]: row
        for row in s3_lake.read_csv("lake", "curated", "fraud_labels.csv")
    }
    if not historical_rows or not labels:
        raise RuntimeError(
            "Faltan historical_transactions.csv o fraud_labels.csv en S3. "
            "Ejecuta make fraud-generate-data-aws primero."
        )
    if not feature_store.read_offline_export("user_behavior_features"):
        feature_store.seed_feature_store()

    contract = default_contract()
    feature_order = load_feature_order()
    dataset: list[dict[str, Any]] = []

    for row in historical_rows:
        label = labels.get(row["transaction_id"])
        if not label:
            continue
        current_features, warnings = build_current_transaction_features(row)
        offline_features = feature_store.get_many_offline_for_transaction(row)
        vector = assemble_feature_vector(
            row,
            current_features,
            offline_features,
            contract,
            warnings,
        )
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

    output = s3_lake.put_csv(
        ("retraining", "training_dataset.csv"),
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
    result = {"training_dataset": output}
    print("Retraining dataset cloud:")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    argparse.ArgumentParser(
        description="Build AWS-backed fraud retraining dataset with point-in-time joins."
    ).parse_args()
    build_retraining_dataset_aws()


if __name__ == "__main__":
    main()

