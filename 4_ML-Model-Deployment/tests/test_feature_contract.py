import pytest

from src.config import ConfigError, FeatureContract
from src.feature_transformations import (
    build_realtime_payload_from_feature_record,
    generate_synthetic_source_dataframe,
    transform_dataframe,
)


def test_feature_contract_from_mapping():
    contract = FeatureContract.from_mapping(
        {
            "inference_features": ["f1", "f2"],
            "training_features": ["f1", "f2", "target"],
            "target_column": "target",
            "batch_identifier_column": "customer_id",
            "realtime_lookup_key": "customer_id",
        }
    )
    assert contract.inference_features == ["f1", "f2"]
    assert contract.target_column == "target"


def test_feature_contract_rejects_target_in_inference_features():
    with pytest.raises(ConfigError):
        FeatureContract.from_mapping(
            {
                "inference_features": ["f1", "target"],
                "target_column": "target",
                "batch_identifier_column": "customer_id",
                "realtime_lookup_key": "customer_id",
            }
        )


def test_same_transformation_supports_offline_and_online_payloads():
    contract = FeatureContract.standalone()
    raw = generate_synthetic_source_dataframe(rows=1, contract=contract)
    transformed = transform_dataframe(raw, contract)
    feature_record = transformed.iloc[0].to_dict()
    payload = build_realtime_payload_from_feature_record(
        feature_record,
        record_id=feature_record[contract.record_identifier_name],
        request_id="req-1",
        contract=contract,
    )

    assert contract.target_column in transformed.columns
    assert contract.target_column not in payload["features"]
    assert set(payload["features"]) == set(contract.inference_features)
