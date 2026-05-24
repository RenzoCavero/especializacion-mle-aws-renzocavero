from src.api.schemas import TransactionRequest


def test_transaction_request_schema_defaults() -> None:
    payload = TransactionRequest()
    assert payload.customer_id == "cus_12345"
    assert payload.amount >= 0
    assert payload.is_high_risk_merchant in {0, 1}

