from src.build_inference_dataset import build_inference_dataset
from src.build_training_dataset import build_training_dataset
from src.clean_data import clean_all
from src.data_profiling import build_profile
from src.data_quality import validate_raw_data
from src.dataset_card import build_dataset_card, dataset_card_to_markdown
from src.feature_engineering import assert_feature_contract, build_inference_features, build_training_features
from src.generate_sample_data import build_synthetic_data
from src.lineage_report import build_lineage, lineage_to_markdown
from src.schemas import CUSTOMER_COLUMNS, FEATURE_COLUMNS, INFERENCE_TRANSACTION_COLUMNS, TARGET_COLUMN, TRANSACTION_COLUMNS
from src.transform_data import build_curated_dataset


def test_synthetic_data_has_expected_schema_and_quality_signals():
    customers, transactions, inference = build_synthetic_data(
        customers_count=20,
        transactions_count=80,
        inference_count=20,
        seed=7,
    )

    assert list(customers.columns) == CUSTOMER_COLUMNS
    assert list(transactions.columns) == TRANSACTION_COLUMNS
    assert list(inference.columns) == INFERENCE_TRANSACTION_COLUMNS
    assert transactions["transaction_id"].duplicated().sum() > 0
    assert (transactions["amount"].fillna(1) <= 0).sum() > 0

    quality = validate_raw_data(customers, transactions, inference)
    assert quality["summary"]["pipeline_can_continue"] is True
    assert quality["summary"]["warning_failures"] >= 1


def test_cleaning_removes_invalid_rows_and_preserves_known_customers():
    customers, transactions, inference = build_synthetic_data(
        customers_count=20,
        transactions_count=80,
        inference_count=20,
        seed=11,
    )

    cleaned_customers, cleaned_transactions, cleaned_inference = clean_all(customers, transactions, inference)

    assert cleaned_transactions["transaction_id"].duplicated().sum() == 0
    assert (cleaned_transactions["amount"] <= 0).sum() == 0
    assert cleaned_transactions["amount"].isna().sum() == 0
    assert set(cleaned_transactions["customer_id"]).issubset(set(cleaned_customers["customer_id"]))
    assert set(cleaned_inference["customer_id"]).issubset(set(cleaned_customers["customer_id"]))


def test_feature_contract_is_shared_by_training_and_inference():
    customers, transactions, inference = build_synthetic_data(
        customers_count=25,
        transactions_count=100,
        inference_count=25,
        seed=13,
    )
    cleaned_customers, cleaned_transactions, cleaned_inference = clean_all(customers, transactions, inference)
    curated_training = build_curated_dataset(cleaned_transactions, cleaned_customers, include_target=True)
    curated_inference = build_curated_dataset(cleaned_inference, cleaned_customers, include_target=False)

    training_features = build_training_features(curated_training)
    inference_features = build_inference_features(curated_inference)
    training_dataset = build_training_dataset(training_features)
    inference_dataset = build_inference_dataset(inference_features)

    assert_feature_contract(training_dataset, inference_dataset)
    assert TARGET_COLUMN in training_dataset.columns
    assert TARGET_COLUMN not in inference_dataset.columns
    for column in FEATURE_COLUMNS:
        assert column in training_dataset.columns
        assert column in inference_dataset.columns


def test_profile_lineage_and_dataset_card_are_generated():
    customers, transactions, inference = build_synthetic_data(
        customers_count=15,
        transactions_count=60,
        inference_count=15,
        seed=17,
    )
    cleaned_customers, cleaned_transactions, cleaned_inference = clean_all(customers, transactions, inference)
    curated_training = build_curated_dataset(cleaned_transactions, cleaned_customers, include_target=True)
    curated_inference = build_curated_dataset(cleaned_inference, cleaned_customers, include_target=False)
    training_dataset = build_training_dataset(build_training_features(curated_training))
    inference_dataset = build_inference_dataset(build_inference_features(curated_inference))

    profile = build_profile({"customers": customers, "transactions": transactions})
    quality = validate_raw_data(customers, transactions, inference)
    lineage = build_lineage("example-bucket", "ml_data_prep_lab", "ml-data-prep-lab")
    card = build_dataset_card(
        "example-bucket",
        profile,
        quality,
        training_rows=len(training_dataset),
        inference_rows=len(inference_dataset),
    )

    assert "datasets" in profile
    assert "raw" in lineage_to_markdown(lineage)
    assert "Dataset Card" in dataset_card_to_markdown(card)
