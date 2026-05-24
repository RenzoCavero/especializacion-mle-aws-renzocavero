from __future__ import annotations


FEATURE_GROUP_ENTITY_KEYS = {
    "user_profile_features": "user_id",
    "user_behavior_features": "user_id",
    "card_velocity_features": "card_id",
    "merchant_risk_features": "merchant_id",
    "device_features": "device_id",
    "last_transaction_features": "user_id",
}


def entity_key_for_group(feature_group: str) -> str:
    return FEATURE_GROUP_ENTITY_KEYS[feature_group]

