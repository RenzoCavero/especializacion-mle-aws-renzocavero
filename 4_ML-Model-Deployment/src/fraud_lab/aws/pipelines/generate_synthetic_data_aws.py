from __future__ import annotations

import argparse
import json

from fraud_lab.aws.config import load_fraud_aws_config
from fraud_lab.aws.s3_data_lake import S3DataLake
from fraud_lab.common.cleaning import clean_transaction
from fraud_lab.config import default_online_transaction
from fraud_lab.features.feature_contract import contract_to_yaml, default_contract
from fraud_lab.pipelines.cleaned_to_curated import enrich
from fraud_lab.pipelines.generate_synthetic_data import (
    batch_transactions,
    historical_transactions,
    labels,
)


def generate_synthetic_data_aws() -> dict[str, str]:
    config = load_fraud_aws_config(require_operational=False)
    s3_lake = S3DataLake(config)
    historical_raw = historical_transactions()
    batch_raw = batch_transactions()
    historical_cleaned = [clean_transaction(row) for row in historical_raw]
    batch_cleaned = [clean_transaction(row) for row in batch_raw]
    historical_curated = [enrich(row) for row in historical_cleaned]
    batch_curated = [enrich(row) for row in batch_cleaned]
    contract = default_contract()

    outputs = {
        "historical_raw": s3_lake.put_jsonl(
            ("lake", "raw", "historical_transactions.jsonl"),
            historical_raw,
        ),
        "batch_raw": s3_lake.put_jsonl(
            ("lake", "raw", "transactions_to_score_raw.jsonl"),
            batch_raw,
        ),
        "online_sample": s3_lake.put_json(
            ("lake", "raw", "online_transaction.json"),
            default_online_transaction(),
        ),
        "historical_cleaned": s3_lake.put_jsonl(
            ("lake", "cleaned", "historical_transactions.jsonl"),
            historical_cleaned,
        ),
        "batch_cleaned": s3_lake.put_jsonl(
            ("lake", "cleaned", "transactions_to_score.jsonl"),
            batch_cleaned,
        ),
        "historical_curated": s3_lake.put_csv(
            ("lake", "curated", "historical_transactions.csv"),
            historical_curated,
        ),
        "batch_curated": s3_lake.put_csv(
            ("lake", "curated", "transactions_to_score.csv"),
            batch_curated,
        ),
        "labels": s3_lake.put_csv(
            ("lake", "curated", "fraud_labels.csv"),
            labels(),
        ),
        "feature_contract": s3_lake.put_text(
            ("artifacts", "preprocessing", "feature_contract.yaml"),
            contract_to_yaml(contract),
            "text/yaml",
        ),
        "feature_order": s3_lake.put_text(
            ("artifacts", "preprocessing", "feature_order.json"),
            json.dumps(contract.feature_order, indent=2) + "\n",
            "application/json",
        ),
    }
    print("Datos sinteticos cloud escritos en S3:")
    for key, value in outputs.items():
        print(f"- {key}: {value}")
    return outputs


def main() -> None:
    argparse.ArgumentParser(
        description="Generate deterministic fraud data in the AWS S3 data lake."
    ).parse_args()
    generate_synthetic_data_aws()


if __name__ == "__main__":
    main()

