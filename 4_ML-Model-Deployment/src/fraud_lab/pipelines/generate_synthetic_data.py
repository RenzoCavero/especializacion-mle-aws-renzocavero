from __future__ import annotations

import argparse

from fraud_lab.common.io_utils import write_csv, write_json, write_jsonl
from fraud_lab.config import data_dir, default_online_transaction, ensure_fraud_dirs
from fraud_lab.features.feature_contract import write_default_artifacts


def historical_transactions() -> list[dict[str, str]]:
    return [
        {"transaction_id": "T001", "user_id": "U123", "card_id": "C789", "merchant_id": "M999", "device_id": "D123", "amount": "500", "currency": "pen", "category": "Electronics", "channel": "Mobile", "location": "Lima|PE", "timestamp": "17/05/2026 14:20"},
        {"transaction_id": "T002", "user_id": "U456", "card_id": "C101", "merchant_id": "M111", "device_id": "D555", "amount": "80", "currency": "pen", "category": "Grocery", "channel": "Web", "location": "Lima|PE", "timestamp": "17/05/2026 14:45"},
        {"transaction_id": "T003", "user_id": "U123", "card_id": "C789", "merchant_id": "M999", "device_id": "D123", "amount": "950", "currency": "usd", "category": "Travel", "channel": "Mobile", "location": "Miami|US", "timestamp": "17/05/2026 15:30"},
        {"transaction_id": "T004", "user_id": "U456", "card_id": "C101", "merchant_id": "M111", "device_id": "D555", "amount": "42", "currency": "pen", "category": "Grocery", "channel": "Web", "location": "Lima|PE", "timestamp": "17/05/2026 16:00"},
    ]


def batch_transactions() -> list[dict[str, str]]:
    return [
        {"transaction_id": "B001", "user_id": "U123", "card_id": "C789", "merchant_id": "M999", "device_id": "D123", "amount": "500", "currency": "pen", "category": "Electronics", "channel": "Mobile", "location": "Lima|PE", "timestamp": "17/05/2026 14:20"},
        {"transaction_id": "B002", "user_id": "U456", "card_id": "C101", "merchant_id": "M111", "device_id": "D555", "amount": "80", "currency": "pen", "category": "Grocery", "channel": "Web", "location": "Lima|PE", "timestamp": "17/05/2026 14:45"},
        {"transaction_id": "B003", "user_id": "U123", "card_id": "C789", "merchant_id": "M999", "device_id": "D123", "amount": "950", "currency": "usd", "category": "Travel", "channel": "Mobile", "location": "Miami|US", "timestamp": "17/05/2026 15:30"},
    ]


def labels() -> list[dict[str, str]]:
    return [
        {"transaction_id": "T001", "label": "1", "label_source": "chargeback", "label_event_time": "2026-05-20T10:00:00Z"},
        {"transaction_id": "T002", "label": "0", "label_source": "manual_review", "label_event_time": "2026-05-18T09:00:00Z"},
        {"transaction_id": "T003", "label": "1", "label_source": "customer_dispute", "label_event_time": "2026-05-22T11:30:00Z"},
        {"transaction_id": "T004", "label": "0", "label_source": "settled", "label_event_time": "2026-05-18T12:00:00Z"},
    ]


def generate_synthetic_data() -> dict[str, str]:
    ensure_fraud_dirs()
    write_default_artifacts()
    raw = data_dir() / "lake" / "raw"
    curated = data_dir() / "lake" / "curated"
    write_jsonl(raw / "historical_transactions.jsonl", historical_transactions())
    write_jsonl(raw / "transactions_to_score_raw.jsonl", batch_transactions())
    write_json(raw / "online_transaction.json", default_online_transaction())
    write_csv(curated / "fraud_labels.csv", labels())
    output = {
        "historical_raw": str(raw / "historical_transactions.jsonl"),
        "batch_raw": str(raw / "transactions_to_score_raw.jsonl"),
        "online_sample": str(raw / "online_transaction.json"),
        "labels": str(curated / "fraud_labels.csv"),
    }
    print("Datos sinteticos generados.")
    for key, value in output.items():
        print(f"- {key}: {value}")
    return output


def main() -> None:
    argparse.ArgumentParser(description="Generate deterministic local fraud data.").parse_args()
    generate_synthetic_data()


if __name__ == "__main__":
    main()

