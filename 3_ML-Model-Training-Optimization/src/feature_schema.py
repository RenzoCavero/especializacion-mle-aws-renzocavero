from __future__ import annotations

from dataclasses import dataclass
from typing import Any


RECORD_IDENTIFIER_NAME = "customer_id"
EVENT_TIME_FEATURE_NAME = "event_time"
TARGET_COLUMN = "churn_label"


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    feature_type: str
    role: str
    description: str

    def to_sagemaker(self) -> dict[str, str]:
        return {"FeatureName": self.name, "FeatureType": self.feature_type}

    def to_contract(self) -> dict[str, str]:
        return {
            "name": self.name,
            "type": self.feature_type,
            "role": self.role,
            "description": self.description,
        }


FEATURE_DEFINITIONS: tuple[FeatureDefinition, ...] = (
    FeatureDefinition("customer_id", "String", "record_identifier", "Synthetic customer identifier."),
    FeatureDefinition("event_time", "String", "event_time", "ISO-8601 event timestamp for point-in-time features."),
    FeatureDefinition("age_days", "Integral", "feature", "Customer tenure in days."),
    FeatureDefinition("plan_type", "String", "feature", "Subscription plan category."),
    FeatureDefinition("country", "String", "feature", "Customer country code/category."),
    FeatureDefinition("device_type", "String", "feature", "Primary device family."),
    FeatureDefinition("sessions_last_7d", "Integral", "feature", "Sessions observed in the last 7 days."),
    FeatureDefinition("sessions_last_30d", "Integral", "feature", "Sessions observed in the last 30 days."),
    FeatureDefinition("avg_session_duration_last_30d", "Fractional", "feature", "Average session duration in minutes."),
    FeatureDefinition("support_tickets_last_30d", "Integral", "feature", "Support tickets created in the last 30 days."),
    FeatureDefinition("payment_failures_last_90d", "Integral", "feature", "Payment failures in the last 90 days."),
    FeatureDefinition("days_since_last_login", "Integral", "feature", "Days since the last login event."),
    FeatureDefinition("engagement_score", "Fractional", "feature", "Composite engagement score from 0 to 1."),
    FeatureDefinition("churn_label", "Integral", "target", "Binary churn target used only for training and evaluation."),
)

RAW_FEATURE_COLUMNS: tuple[str, ...] = tuple(fd.name for fd in FEATURE_DEFINITIONS)
CATEGORICAL_FEATURES: tuple[str, ...] = ("plan_type", "country", "device_type")
NUMERIC_TRAINING_FEATURES: tuple[str, ...] = (
    "age_days",
    "sessions_last_7d",
    "sessions_last_30d",
    "avg_session_duration_last_30d",
    "support_tickets_last_30d",
    "payment_failures_last_90d",
    "days_since_last_login",
    "engagement_score",
)
TRAINING_FEATURES: tuple[str, ...] = NUMERIC_TRAINING_FEATURES + CATEGORICAL_FEATURES
INFERENCE_FEATURES: tuple[str, ...] = (
    "plan_type",
    "country",
    "device_type",
    "sessions_last_7d",
    "sessions_last_30d",
    "avg_session_duration_last_30d",
    "support_tickets_last_30d",
    "payment_failures_last_90d",
    "days_since_last_login",
    "engagement_score",
)


def sagemaker_feature_definitions() -> list[dict[str, str]]:
    return [feature.to_sagemaker() for feature in FEATURE_DEFINITIONS]


def validate_records_columns(columns: list[str] | tuple[str, ...]) -> None:
    missing = [name for name in RAW_FEATURE_COLUMNS if name not in columns]
    if missing:
        raise ValueError(f"Missing required feature columns: {missing}")


def build_feature_contract(
    *,
    feature_group_name: str,
    online_store_enabled: bool,
    offline_store_s3_uri: str,
    model_package_group_name: str,
    model_artifact_s3_uri: str | None,
    dataset_s3_uri: str | None,
    objective_metric_name: str = "f1",
    objective_metric_value: float | None = None,
    preprocessing_metadata_s3_uri: str | None = None,
    model_package_arn: str | None = None,
    raw_data_s3_uri: str | None = None,
    cleaned_data_s3_uri: str | None = None,
    curated_features_s3_uri: str | None = None,
    feature_lineage_s3_uri: str | None = None,
) -> dict[str, Any]:
    return {
        "feature_group_name": feature_group_name,
        "online_store_enabled": online_store_enabled,
        "offline_store_s3_uri": offline_store_s3_uri,
        "record_identifier_name": RECORD_IDENTIFIER_NAME,
        "event_time_feature_name": EVENT_TIME_FEATURE_NAME,
        "features": [feature.to_contract() for feature in FEATURE_DEFINITIONS],
        "target_column": TARGET_COLUMN,
        "inference_features": list(INFERENCE_FEATURES),
        "training_features": list(TRAINING_FEATURES),
        "categorical_features": list(CATEGORICAL_FEATURES),
        "numeric_training_features": list(NUMERIC_TRAINING_FEATURES),
        "batch_inference_source": "offline_store",
        "realtime_lookup_key": RECORD_IDENTIFIER_NAME,
        "model_package_group_name": model_package_group_name,
        "model_package_arn": model_package_arn,
        "model_artifact_s3_uri": model_artifact_s3_uri,
        "dataset_s3_uri": dataset_s3_uri,
        "source_data": {
            "raw_s3_uri": raw_data_s3_uri,
            "cleaned_s3_uri": cleaned_data_s3_uri,
            "curated_features_s3_uri": curated_features_s3_uri,
            "feature_lineage_s3_uri": feature_lineage_s3_uri,
        },
        "preprocessing_metadata_s3_uri": preprocessing_metadata_s3_uri,
        "objective_metric_name": objective_metric_name,
        "objective_metric_value": objective_metric_value,
        "model_approval_status": "PendingManualApproval",
        "future_labs": {
            "batch_inference": {
                "source": "Feature Store Offline Store or processed batch dataset derived from it",
                "exclude_columns": [TARGET_COLUMN],
            },
            "real_time_inference": {
                "source": "Feature Store Online Store",
                "lookup_key": RECORD_IDENTIFIER_NAME,
                "exclude_columns": [TARGET_COLUMN],
            },
        },
    }
