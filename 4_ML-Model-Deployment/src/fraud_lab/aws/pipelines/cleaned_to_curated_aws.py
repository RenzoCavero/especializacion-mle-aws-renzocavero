from __future__ import annotations

import argparse

from fraud_lab.aws.config import load_fraud_aws_config
from fraud_lab.aws.s3_data_lake import S3DataLake
from fraud_lab.pipelines.cleaned_to_curated import enrich


def cleaned_to_curated_aws() -> dict[str, str]:
    config = load_fraud_aws_config(require_operational=False)
    s3_lake = S3DataLake(config)
    outputs: dict[str, str] = {}
    for input_name, output_name in (
        ("historical_transactions", "historical_transactions"),
        ("transactions_to_score", "transactions_to_score"),
    ):
        rows = [
            enrich(row)
            for row in s3_lake.read_jsonl("lake", "cleaned", f"{input_name}.jsonl")
        ]
        outputs[output_name] = s3_lake.put_csv(
            ("lake", "curated", f"{output_name}.csv"),
            rows,
        )
    print("Cleaned -> curated cloud completado:")
    for key, value in outputs.items():
        print(f"- {key}: {value}")
    return outputs


def main() -> None:
    argparse.ArgumentParser(
        description="Build AWS S3 curated transaction tables from cleaned events."
    ).parse_args()
    cleaned_to_curated_aws()


if __name__ == "__main__":
    main()

