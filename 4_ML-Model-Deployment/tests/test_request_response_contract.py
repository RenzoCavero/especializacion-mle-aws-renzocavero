import pytest

from src.config import FeatureContract
from src.validate_request_response import (
    ContractError,
    example_request,
    normalize_response,
    validate_inference_request,
    validate_model_response,
)


def test_valid_request_contract():
    contract = FeatureContract.standalone()
    payload = example_request(contract)
    features = validate_inference_request(payload, contract)
    assert set(features) == set(contract.inference_features)


def test_target_column_is_rejected():
    contract = FeatureContract.standalone()
    payload = example_request(contract)
    payload["features"][contract.target_column] = 1
    with pytest.raises(ContractError):
        validate_inference_request(payload, contract)


def test_response_contract_normalizes_score():
    response = normalize_response({"score": 0.82}, model_version="v1", request_id="req-1")
    assert response["predicted_label"] == 1
    assert response["decision"] == "review"
    assert validate_model_response(response)["request_id"] == "req-1"
