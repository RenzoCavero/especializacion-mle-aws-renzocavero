from __future__ import annotations


FEATURE_GROUPS = {
    "user_profile_features": {
        "entity_key": "user_id",
        "features": [
            "account_age_days",
            "customer_segment_premium",
            "customer_segment_standard",
            "kyc_level_full",
            "user_country_risk_score",
        ],
    },
    "user_behavior_features": {
        "entity_key": "user_id",
        "features": [
            "user_txn_count_1h",
            "user_txn_count_24h",
            "user_avg_amount_30d",
            "user_max_amount_30d",
            "distinct_merchants_7d",
            "user_risk_score",
        ],
    },
    "card_velocity_features": {
        "entity_key": "card_id",
        "features": [
            "card_txn_count_5m",
            "card_txn_count_1h",
            "card_amount_sum_1h",
            "card_declined_count_1h",
            "card_countries_count_24h",
        ],
    },
    "merchant_risk_features": {
        "entity_key": "merchant_id",
        "features": [
            "merchant_age_days",
            "merchant_category_risk",
            "merchant_fraud_rate_30d",
            "merchant_chargeback_count_30d",
            "merchant_risk_score",
            "is_high_risk_mcc",
        ],
    },
    "device_features": {
        "entity_key": "device_id",
        "features": [
            "device_age_days",
            "device_type_mobile",
            "device_users_count_7d",
            "device_trust_score",
            "is_emulator",
        ],
    },
    "last_transaction_features": {
        "entity_key": "user_id",
        "features": [
            "last_transaction_amount",
            "last_transaction_country",
            "last_transaction_timestamp",
            "last_channel_used",
            "last_merchant_id",
            "last_device_id",
        ],
    },
}


def entity_key(feature_group: str) -> str:
    return FEATURE_GROUPS[feature_group]["entity_key"]


def feature_names(feature_group: str) -> list[str]:
    return list(FEATURE_GROUPS[feature_group]["features"])

