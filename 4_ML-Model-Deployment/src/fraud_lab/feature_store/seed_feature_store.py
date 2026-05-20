from __future__ import annotations

import argparse
from typing import Any

from fraud_lab.feature_store.offline_store import LocalOfflineFeatureStore
from fraud_lab.feature_store.feature_groups import entity_key
from fraud_lab.feature_store.online_store import LocalOnlineFeatureStore
from fraud_lab.features.feature_contract import write_default_artifacts


def baseline_feature_records() -> dict[str, list[dict[str, Any]]]:
    return {
        "user_profile_features": [
            {
                "user_id": "U123",
                "event_time": "2026-05-17T10:00:00Z",
                "account_age_days": 730,
                "customer_segment_premium": 1,
                "customer_segment_standard": 0,
                "kyc_level_full": 1,
                "user_country_risk_score": 0.21,
            },
            {
                "user_id": "U456",
                "event_time": "2026-05-17T10:00:00Z",
                "account_age_days": 80,
                "customer_segment_premium": 0,
                "customer_segment_standard": 1,
                "kyc_level_full": 0,
                "user_country_risk_score": 0.11,
            },
        ],
        "user_behavior_features": [
            {"user_id": "U123", "event_time": "2026-05-17T13:00:00Z", "user_txn_count_1h": 2, "user_txn_count_24h": 12, "user_avg_amount_30d": 80.0, "user_max_amount_30d": 430.0, "distinct_merchants_7d": 7, "user_risk_score": 0.16},
            {"user_id": "U123", "event_time": "2026-05-17T14:00:00Z", "user_txn_count_1h": 4, "user_txn_count_24h": 18, "user_avg_amount_30d": 87.5, "user_max_amount_30d": 520.0, "distinct_merchants_7d": 9, "user_risk_score": 0.18},
            {"user_id": "U123", "event_time": "2026-05-17T15:00:00Z", "user_txn_count_1h": 7, "user_txn_count_24h": 21, "user_avg_amount_30d": 91.0, "user_max_amount_30d": 650.0, "distinct_merchants_7d": 10, "user_risk_score": 0.22},
            {"user_id": "U456", "event_time": "2026-05-17T14:00:00Z", "user_txn_count_1h": 1, "user_txn_count_24h": 3, "user_avg_amount_30d": 65.0, "user_max_amount_30d": 120.0, "distinct_merchants_7d": 2, "user_risk_score": 0.07},
        ],
        "card_velocity_features": [
            {"card_id": "C789", "event_time": "2026-05-17T14:00:00Z", "card_txn_count_5m": 3, "card_txn_count_1h": 9, "card_amount_sum_1h": 1450.0, "card_declined_count_1h": 2, "card_countries_count_24h": 3},
            {"card_id": "C101", "event_time": "2026-05-17T14:00:00Z", "card_txn_count_5m": 0, "card_txn_count_1h": 1, "card_amount_sum_1h": 80.0, "card_declined_count_1h": 0, "card_countries_count_24h": 1},
        ],
        "merchant_risk_features": [
            {"merchant_id": "M999", "event_time": "2026-05-17T00:00:00Z", "merchant_age_days": 120, "merchant_category_risk": 0.72, "merchant_fraud_rate_30d": 0.032, "merchant_chargeback_count_30d": 27, "merchant_risk_score": 0.71, "is_high_risk_mcc": 1},
            {"merchant_id": "M111", "event_time": "2026-05-17T00:00:00Z", "merchant_age_days": 1300, "merchant_category_risk": 0.08, "merchant_fraud_rate_30d": 0.004, "merchant_chargeback_count_30d": 2, "merchant_risk_score": 0.09, "is_high_risk_mcc": 0},
        ],
        "device_features": [
            {"device_id": "D123", "event_time": "2026-05-17T14:10:00Z", "device_age_days": 2, "device_type_mobile": 1, "device_users_count_7d": 8, "device_trust_score": 0.35, "is_emulator": 0},
            {"device_id": "D555", "event_time": "2026-05-17T14:10:00Z", "device_age_days": 500, "device_type_mobile": 0, "device_users_count_7d": 1, "device_trust_score": 0.91, "is_emulator": 0},
        ],
    }


def seed_feature_store() -> dict[str, int]:
    write_default_artifacts()
    online = LocalOnlineFeatureStore()
    offline = LocalOfflineFeatureStore()
    counts: dict[str, int] = {}
    for group, records in baseline_feature_records().items():
        offline.replace_records(group, records)
        latest_by_entity: dict[str, dict[str, Any]] = {}
        entity_key_name = entity_key(group)
        for record in records:
            latest_by_entity[str(record[entity_key_name])] = record
        for record in latest_by_entity.values():
            online.put_record(group, record)
        counts[group] = len(records)
    return counts


def main() -> None:
    argparse.ArgumentParser(description="Seed local Online Store and Offline Store.").parse_args()
    counts = seed_feature_store()
    print("Feature Store local cargado:")
    for group, count in counts.items():
        print(f"- {group}: {count} offline records")


if __name__ == "__main__":
    main()
