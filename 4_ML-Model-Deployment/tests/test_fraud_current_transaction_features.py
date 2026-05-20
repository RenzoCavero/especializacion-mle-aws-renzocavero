from fraud_lab.common.cleaning import clean_transaction
from fraud_lab.features.current_transaction_features import build_current_transaction_features


def test_current_transaction_features_are_stable_for_known_values():
    cleaned = clean_transaction(
        {
            "transaction_id": "T001",
            "user_id": "U123",
            "card_id": "C789",
            "merchant_id": "M999",
            "device_id": "D123",
            "amount": "500",
            "currency": "pen",
            "category": "Electronics",
            "channel": "Mobile",
            "location": "Lima|PE",
            "timestamp": "17/05/2026 14:20",
        }
    )
    features, warnings = build_current_transaction_features(cleaned)

    assert features["hour_of_day"] == 14.0
    assert features["is_weekend"] == 1.0
    assert features["category_electronics"] == 1.0
    assert features["channel_mobile"] == 1.0
    assert warnings == []


def test_unknown_category_does_not_create_dynamic_column():
    cleaned = clean_transaction(
        {
            "transaction_id": "T005",
            "user_id": "U123",
            "card_id": "C789",
            "merchant_id": "M999",
            "device_id": "D123",
            "amount": "100",
            "currency": "pen",
            "category": "Crypto",
            "channel": "Mobile",
            "location": "Lima|PE",
            "timestamp": "18/05/2026 10:00",
        }
    )
    features, warnings = build_current_transaction_features(cleaned)

    assert "category_crypto" not in features
    assert features["category_electronics"] == 0.0
    assert warnings

