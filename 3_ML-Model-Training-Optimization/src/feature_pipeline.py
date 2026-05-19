from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

import pandas as pd

try:
    from src.feature_schema import (
        CATEGORICAL_FEATURES,
        EVENT_TIME_FEATURE_NAME,
        FEATURE_DEFINITIONS,
        RAW_FEATURE_COLUMNS,
        RECORD_IDENTIFIER_NAME,
        TARGET_COLUMN,
        validate_records_columns,
    )
except ModuleNotFoundError:  # pragma: no cover - used inside SageMaker Processing input mount.
    from feature_schema import (  # type: ignore
        CATEGORICAL_FEATURES,
        EVENT_TIME_FEATURE_NAME,
        FEATURE_DEFINITIONS,
        RAW_FEATURE_COLUMNS,
        RECORD_IDENTIFIER_NAME,
        TARGET_COLUMN,
        validate_records_columns,
    )


INTEGRAL_FEATURES = {
    feature.name
    for feature in FEATURE_DEFINITIONS
    if feature.feature_type == "Integral"
}
FRACTIONAL_FEATURES = {
    feature.name
    for feature in FEATURE_DEFINITIONS
    if feature.feature_type == "Fractional"
}


def clean_raw_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    validate_records_columns(list(df.columns))
    cleaned = df.loc[:, list(RAW_FEATURE_COLUMNS)].copy()

    transformations = [
        "Select only columns declared in the Feature Store contract.",
        "Trim categorical/string columns and normalize event_time to UTC ISO-8601.",
        "Validate numeric feature types and remove duplicated customer_id/event_time pairs.",
    ]

    for column in (RECORD_IDENTIFIER_NAME, *CATEGORICAL_FEATURES):
        cleaned[column] = cleaned[column].astype(str).str.strip()

    event_time = pd.to_datetime(cleaned[EVENT_TIME_FEATURE_NAME], utc=True, errors="coerce")
    if event_time.isna().any():
        bad_rows = int(event_time.isna().sum())
        raise ValueError(f"{bad_rows} rows have invalid event_time values.")
    # SageMaker Feature Store accepts UTC event times with the literal Z suffix.
    cleaned[EVENT_TIME_FEATURE_NAME] = event_time.dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    for column in INTEGRAL_FEATURES:
        values = pd.to_numeric(cleaned[column], errors="coerce")
        if values.isna().any():
            raise ValueError(f"Column {column} contains non numeric values.")
        cleaned[column] = values.astype(int)

    for column in FRACTIONAL_FEATURES:
        values = pd.to_numeric(cleaned[column], errors="coerce")
        if values.isna().any():
            raise ValueError(f"Column {column} contains non numeric values.")
        cleaned[column] = values.astype(float)

    cleaned = cleaned.drop_duplicates(
        subset=[RECORD_IDENTIFIER_NAME, EVENT_TIME_FEATURE_NAME],
        keep="last",
    )
    cleaned = cleaned.sort_values([RECORD_IDENTIFIER_NAME, EVENT_TIME_FEATURE_NAME]).reset_index(drop=True)
    return cleaned, transformations


def curate_cleaned_frame(cleaned: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    curated = cleaned.copy()

    transformations = [
        "Clip feature ranges to operational limits expected by the model.",
        "Recompute engagement_score from curated behavioral signals.",
        "Keep churn_label as training target for the lab Offline Store dataset.",
    ]

    curated["sessions_last_7d"] = curated["sessions_last_7d"].clip(lower=0, upper=120)
    curated["sessions_last_30d"] = curated["sessions_last_30d"].clip(lower=0, upper=400)
    curated["avg_session_duration_last_30d"] = curated["avg_session_duration_last_30d"].clip(lower=0, upper=180)
    curated["support_tickets_last_30d"] = curated["support_tickets_last_30d"].clip(lower=0, upper=30)
    curated["payment_failures_last_90d"] = curated["payment_failures_last_90d"].clip(lower=0, upper=20)
    curated["days_since_last_login"] = curated["days_since_last_login"].clip(lower=0, upper=365)

    plan_boost = curated["plan_type"].ne("free").astype(float)
    curated["engagement_score"] = (
        0.30 * (curated["sessions_last_30d"] / 60).clip(0, 1)
        + 0.20 * (curated["sessions_last_7d"] / 18).clip(0, 1)
        + 0.20 * (curated["avg_session_duration_last_30d"] / 60).clip(0, 1)
        + 0.20 * (1 - (curated["days_since_last_login"] / 90).clip(0, 1))
        + 0.10 * plan_boost
    ).clip(0, 1).round(4)

    curated[TARGET_COLUMN] = curated[TARGET_COLUMN].astype(int).clip(0, 1)
    return curated.loc[:, list(RAW_FEATURE_COLUMNS)], transformations


def curate_feature_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    cleaned, cleaning_steps = clean_raw_frame(df)
    curated, curation_steps = curate_cleaned_frame(cleaned)
    return curated, [*cleaning_steps, *curation_steps]


def _value_as_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def row_to_feature_record(row: pd.Series) -> list[dict[str, str]]:
    return [
        {"FeatureName": feature.name, "ValueAsString": _value_as_string(row[feature.name])}
        for feature in FEATURE_DEFINITIONS
    ]


def feature_lineage_document(
    *,
    raw_s3_uri: str,
    cleaned_s3_uri: str,
    curated_s3_uri: str,
    feature_group_name: str,
    transformations: list[str],
    row_counts: dict[str, int],
    producer: str,
    processing_job_name: str | None = None,
) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "producer": producer,
        "processing_job_name": processing_job_name,
        "feature_group_name": feature_group_name,
        "sources": {
            "raw": raw_s3_uri,
            "cleaned": cleaned_s3_uri,
            "curated": curated_s3_uri,
        },
        "target": {
            "feature_store": feature_group_name,
            "record_identifier": RECORD_IDENTIFIER_NAME,
            "event_time": EVENT_TIME_FEATURE_NAME,
        },
        "row_counts": row_counts,
        "transformations": transformations,
        "notes": [
            "SageMaker Feature Store writes Online Store synchronously for latest lookups.",
            "SageMaker Feature Store writes Offline Store to S3 asynchronously for historical training datasets.",
        ],
    }
