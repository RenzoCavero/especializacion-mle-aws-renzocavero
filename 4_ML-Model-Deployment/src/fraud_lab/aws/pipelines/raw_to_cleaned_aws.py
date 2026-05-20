from __future__ import annotations

import argparse

from fraud_lab.aws.config import load_fraud_aws_config
from fraud_lab.aws.s3_data_lake import S3DataLake
from fraud_lab.common.cleaning import clean_transaction


def raw_to_cleaned_aws() -> dict[str, str]:
    config = load_fraud_aws_config(require_operational=False)
    s3_lake = S3DataLake(config)
    outputs: dict[str, str] = {}
    for input_name, output_name in (
        ("historical_transactions", "historical_transactions"),
        ("transactions_to_score_raw", "transactions_to_score"),
    ):
        rows = [
            clean_transaction(row)
            for row in s3_lake.read_jsonl("lake", "raw", f"{input_name}.jsonl")
        ]
        outputs[output_name] = s3_lake.put_jsonl(
            ("lake", "cleaned", f"{output_name}.jsonl"),
            rows,
        )
    print("Raw -> cleaned cloud completado:")
    for key, value in outputs.items():
        print(f"- {key}: {value}")
    return outputs


def main() -> None:
    argparse.ArgumentParser(
        description="Convert AWS S3 raw transaction events to cleaned layer."
    ).parse_args()
    raw_to_cleaned_aws()


if __name__ == "__main__":
    main()

