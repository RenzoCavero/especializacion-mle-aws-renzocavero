from src.feature_schema import (
    EVENT_TIME_FEATURE_NAME,
    INFERENCE_FEATURES,
    RECORD_IDENTIFIER_NAME,
    TARGET_COLUMN,
    TRAINING_FEATURES,
    build_feature_contract,
    sagemaker_feature_definitions,
)


def test_schema_contains_identifier_event_time_and_target() -> None:
    names = [item["FeatureName"] for item in sagemaker_feature_definitions()]
    assert RECORD_IDENTIFIER_NAME in names
    assert EVENT_TIME_FEATURE_NAME in names
    assert TARGET_COLUMN in names


def test_target_is_not_in_inference_features() -> None:
    assert TARGET_COLUMN not in INFERENCE_FEATURES
    assert TARGET_COLUMN not in TRAINING_FEATURES


def test_feature_contract_has_future_lab_metadata() -> None:
    contract = build_feature_contract(
        feature_group_name="churn-customer-features",
        online_store_enabled=True,
        offline_store_s3_uri="s3://bucket/feature-store-offline/",
        model_package_group_name="churn-model-package-group",
        model_artifact_s3_uri="s3://bucket/output/best_model/model.tar.gz",
        dataset_s3_uri="s3://bucket/input/train/",
    )
    assert contract["batch_inference_source"] == "offline_store"
    assert contract["realtime_lookup_key"] == RECORD_IDENTIFIER_NAME
    assert contract["future_labs"]["real_time_inference"]["source"] == "Feature Store Online Store"
