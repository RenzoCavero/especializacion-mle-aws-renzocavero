from fraud_lab.features.feature_contract import default_contract
from fraud_lab.features.feature_vector import assemble_feature_vector


def test_feature_vector_respects_order_and_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("FRAUD_LAB_ROOT", str(tmp_path))
    contract = default_contract()
    cleaned = {
        "transaction_id": "T001",
        "timestamp": "2026-05-17T14:20:00Z",
    }
    current = {
        "amount_normalized": 500.0,
        "currency_normalized_amount": 500.0,
        "hour_of_day": 14.0,
        "day_of_week": 6.0,
        "is_weekend": 1.0,
        "category_electronics": 1.0,
        "category_travel": 0.0,
        "category_grocery": 0.0,
        "channel_mobile": 1.0,
        "channel_web": 0.0,
        "is_cross_border": 0.0,
    }
    vector = assemble_feature_vector(cleaned, current, {}, contract)

    assert list(vector.values) == contract.feature_order
    assert len(vector.ordered_values) == len(contract.feature_order)
    assert vector.values["user_txn_count_1h"] == 0.0
    assert any("user_txn_count_1h" in warning for warning in vector.warnings)

