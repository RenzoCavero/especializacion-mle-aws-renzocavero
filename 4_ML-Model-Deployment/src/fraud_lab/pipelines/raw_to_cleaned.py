from __future__ import annotations

import argparse

from fraud_lab.common.cleaning import clean_transaction
from fraud_lab.common.io_utils import read_jsonl, write_jsonl
from fraud_lab.config import data_dir, ensure_fraud_dirs


def raw_to_cleaned() -> dict[str, str]:
    ensure_fraud_dirs()
    raw = data_dir() / "lake" / "raw"
    cleaned_dir = data_dir() / "lake" / "cleaned"
    outputs: dict[str, str] = {}
    for file_name in ("historical_transactions", "transactions_to_score_raw"):
        rows = [clean_transaction(row) for row in read_jsonl(raw / f"{file_name}.jsonl")]
        output_name = file_name.replace("_raw", "")
        output_path = cleaned_dir / f"{output_name}.jsonl"
        write_jsonl(output_path, rows)
        outputs[output_name] = str(output_path)
    print("Raw -> cleaned completado.")
    for key, value in outputs.items():
        print(f"- {key}: {value}")
    return outputs


def main() -> None:
    argparse.ArgumentParser(description="Convert raw transaction events to cleaned layer.").parse_args()
    raw_to_cleaned()


if __name__ == "__main__":
    main()

