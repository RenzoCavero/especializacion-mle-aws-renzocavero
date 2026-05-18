from __future__ import annotations

import argparse
from typing import Any

from fraud_lab.common.io_utils import append_jsonl, read_json, write_csv
from fraud_lab.config import data_dir, ensure_fraud_dirs
from fraud_lab.feature_store.offline_store import LocalOfflineFeatureStore
from fraud_lab.feature_store.online_store import LocalOnlineFeatureStore
from fraud_lab.pipelines.cleaned_to_curated import enrich


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _updated_records(cleaned: dict[str, Any], online: LocalOnlineFeatureStore) -> dict[str, dict[str, Any]]:
    amount = _float(cleaned["amount_pen"])
    user_behavior = online.get_record("user_behavior_features", cleaned["user_id"])
    card_velocity = online.get_record("card_velocity_features", cleaned["card_id"])
    user_count = _int(user_behavior.get("user_txn_count_1h")) + 1
    old_avg = _float(user_behavior.get("user_avg_amount_30d"), amount)
    new_avg = round(((old_avg * max(user_count - 1, 1)) + amount) / max(user_count, 1), 4)
    updated_user = {
        "user_id": cleaned["user_id"],
        "event_time": cleaned["timestamp"],
        "user_txn_count_1h": user_count,
        "user_txn_count_24h": _int(user_behavior.get("user_txn_count_24h")) + 1,
        "user_avg_amount_30d": new_avg,
        "user_max_amount_30d": max(_float(user_behavior.get("user_max_amount_30d")), amount),
        "distinct_merchants_7d": max(_int(user_behavior.get("distinct_merchants_7d")), 1),
        "user_risk_score": min(_float(user_behavior.get("user_risk_score")) + 0.01, 1.0),
    }
    updated_card = {
        "card_id": cleaned["card_id"],
        "event_time": cleaned["timestamp"],
        "card_txn_count_5m": _int(card_velocity.get("card_txn_count_5m")) + 1,
        "card_txn_count_1h": _int(card_velocity.get("card_txn_count_1h")) + 1,
        "card_amount_sum_1h": round(_float(card_velocity.get("card_amount_sum_1h")) + amount, 4),
        "card_declined_count_1h": _int(card_velocity.get("card_declined_count_1h")),
        "card_countries_count_24h": max(_int(card_velocity.get("card_countries_count_24h")), 1),
    }
    last_transaction = {
        "user_id": cleaned["user_id"],
        "event_time": cleaned["timestamp"],
        "last_transaction_amount": amount,
        "last_transaction_country": cleaned["country"],
        "last_transaction_timestamp": cleaned["timestamp"],
        "last_channel_used": cleaned["channel"],
        "last_merchant_id": cleaned["merchant_id"],
        "last_device_id": cleaned["device_id"],
    }
    return {
        "user_behavior_features": updated_user,
        "card_velocity_features": updated_card,
        "last_transaction_features": last_transaction,
    }


def async_update_online_features() -> dict[str, int]:
    ensure_fraud_dirs()
    pending_dir = data_dir() / "events" / "pending"
    processed_dir = data_dir() / "events" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    online = LocalOnlineFeatureStore()
    offline = LocalOfflineFeatureStore()
    processed = 0

    for event_file in sorted(pending_dir.glob("*.json")):
        event = read_json(event_file)
        raw = event["raw_event"]
        cleaned = event["cleaned_event"]
        curated = enrich(cleaned)
        append_jsonl(data_dir() / "lake" / "raw" / "async_transactions.jsonl", raw)
        append_jsonl(data_dir() / "lake" / "cleaned" / "async_transactions.jsonl", cleaned)
        append_jsonl(data_dir() / "lake" / "curated" / "async_transactions.jsonl", curated)
        for group, record in _updated_records(cleaned, online).items():
            online.put_record(group, record)
            offline.put_records(group, [record])
        event_file.rename(processed_dir / event_file.name)
        processed += 1

    summary = [{"processed_events": processed}]
    write_csv(data_dir() / "events" / "async_update_summary.csv", summary)
    print(f"Eventos asincronos procesados: {processed}")
    return {"processed_events": processed}


def main() -> None:
    argparse.ArgumentParser(description="Process pending prediction events and update future features.").parse_args()
    async_update_online_features()


if __name__ == "__main__":
    main()

