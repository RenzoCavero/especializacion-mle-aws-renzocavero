from fraud_lab.common.cleaning import clean_transaction


def test_cleaning_canonicalizes_transaction():
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

    assert cleaned["amount"] == 500.0
    assert cleaned["currency"] == "PEN"
    assert cleaned["city"] == "Lima"
    assert cleaned["country"] == "PE"
    assert cleaned["timestamp"] == "2026-05-17T14:20:00Z"
    assert cleaned["category"] == "electronics"

