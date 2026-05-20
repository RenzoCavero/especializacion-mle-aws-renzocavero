from __future__ import annotations

import argparse
from typing import Any

from fraud_lab.common.io_utils import read_jsonl, write_csv
from fraud_lab.config import data_dir, ensure_fraud_dirs


USER_PROFILE = {
    "U123": {"customer_segment": "premium", "account_age_days": 730, "kyc_level": "full"},
    "U456": {"customer_segment": "standard", "account_age_days": 80, "kyc_level": "basic"},
}

MERCHANT_PROFILE = {
    "M999": {"merchant_category": "electronics", "merchant_status": "active"},
    "M111": {"merchant_category": "grocery", "merchant_status": "active"},
}


def enrich(cleaned: dict[str, Any]) -> dict[str, Any]:
    user = USER_PROFILE.get(cleaned["user_id"], {"customer_segment": "standard", "account_age_days": 0, "kyc_level": "unknown"})
    merchant = MERCHANT_PROFILE.get(cleaned["merchant_id"], {"merchant_category": cleaned["category"], "merchant_status": "unknown"})
    return {
        **cleaned,
        **user,
        **merchant,
        "transaction_country": cleaned["country"],
        "transaction_status": "approved",
    }


def cleaned_to_curated() -> dict[str, str]:
    ensure_fraud_dirs()
    cleaned_dir = data_dir() / "lake" / "cleaned"
    curated_dir = data_dir() / "lake" / "curated"
    outputs: dict[str, str] = {}
    for input_name, output_name in (
        ("historical_transactions", "historical_transactions"),
        ("transactions_to_score", "transactions_to_score"),
    ):
        rows = [enrich(row) for row in read_jsonl(cleaned_dir / f"{input_name}.jsonl")]
        output_path = curated_dir / f"{output_name}.csv"
        write_csv(output_path, rows)
        outputs[output_name] = str(output_path)
    print("Cleaned -> curated completado.")
    for key, value in outputs.items():
        print(f"- {key}: {value}")
    return outputs


def main() -> None:
    argparse.ArgumentParser(description="Build curated business-ready transaction tables.").parse_args()
    cleaned_to_curated()


if __name__ == "__main__":
    main()

