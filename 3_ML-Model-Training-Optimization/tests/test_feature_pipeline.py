from __future__ import annotations

from src.feature_pipeline import clean_raw_frame, curate_feature_frame, feature_lineage_document
from src.feature_schema import RAW_FEATURE_COLUMNS, TARGET_COLUMN
from src.generate_sample_data import generate_churn_dataset


def test_clean_and_curate_preserve_contract_columns() -> None:
    raw = generate_churn_dataset(rows=20, seed=7)

    cleaned, cleaning_steps = clean_raw_frame(raw)
    curated, curation_steps = curate_feature_frame(cleaned)

    assert list(cleaned.columns) == list(RAW_FEATURE_COLUMNS)
    assert list(curated.columns) == list(RAW_FEATURE_COLUMNS)
    assert len(cleaning_steps) > 0
    assert len(curation_steps) > len(cleaning_steps)
    assert cleaned["event_time"].str.endswith("Z").all()
    assert "+0000" not in cleaned["event_time"].iloc[0]
    assert curated["engagement_score"].between(0, 1).all()
    assert set(curated[TARGET_COLUMN].unique()).issubset({0, 1})


def test_feature_lineage_document_records_sources() -> None:
    lineage = feature_lineage_document(
        raw_s3_uri="s3://bucket/raw/churn_raw.csv",
        cleaned_s3_uri="s3://bucket/cleaned/churn_cleaned.csv",
        curated_s3_uri="s3://bucket/curated/churn_features.csv",
        feature_group_name="churn-customer-features",
        transformations=["clean", "curate"],
        row_counts={"raw": 10, "curated": 10},
        producer="unit-test",
    )

    assert lineage["sources"]["raw"].endswith("raw/churn_raw.csv")
    assert lineage["sources"]["cleaned"].endswith("cleaned/churn_cleaned.csv")
    assert lineage["sources"]["curated"].endswith("curated/churn_features.csv")
    assert lineage["target"]["feature_store"] == "churn-customer-features"
