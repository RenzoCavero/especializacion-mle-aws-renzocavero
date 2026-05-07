"""Shared feature engineering logic for training and inference."""

from __future__ import annotations

import pandas as pd

from src.schemas import FEATURE_COLUMNS, INFERENCE_COLUMNS, TARGET_COLUMN, TRAINING_COLUMNS


CHANNELS = ["atm", "card_present", "mobile", "online", "wire"]
SEGMENTS = ["premium", "retail", "smb"]
MERCHANTS = ["electronics", "fuel", "grocery", "travel", "utilities"]
HIGH_RISK_COUNTRIES = {"US", "BR"}


def _add_indicator_columns(df: pd.DataFrame, source_column: str, values: list[str], prefix: str) -> pd.DataFrame:
    for value in values:
        df[f"{prefix}_{value}"] = (df[source_column].astype(str) == value).astype(int)
    return df


def build_feature_frame(curated: pd.DataFrame, include_target: bool) -> pd.DataFrame:
    features = curated.copy()
    customer_stats = (
        features.groupby("customer_id")["amount"]
        .agg(customer_txn_count="count", customer_avg_amount="mean", customer_max_amount="max")
        .reset_index()
    )
    features = features.merge(customer_stats, on="customer_id", how="left")
    features["customer_avg_amount"] = features["customer_avg_amount"].fillna(features["amount"].median())
    features["customer_max_amount"] = features["customer_max_amount"].fillna(features["amount"])
    features["amount_to_customer_avg"] = features["amount"] / features["customer_avg_amount"].replace(0, 1)
    features["high_risk_country"] = features["country"].isin(HIGH_RISK_COUNTRIES).astype(int)

    features = _add_indicator_columns(features, "channel", CHANNELS, "channel")
    features = _add_indicator_columns(features, "segment", SEGMENTS, "segment")
    features = _add_indicator_columns(features, "merchant_category", MERCHANTS, "merchant")

    for column in FEATURE_COLUMNS:
        if column not in features.columns:
            features[column] = 0
        features[column] = pd.to_numeric(features[column], errors="coerce").fillna(0)

    if include_target:
        features[TARGET_COLUMN] = pd.to_numeric(features[TARGET_COLUMN], errors="coerce").fillna(0).astype(int)
        output = features[["transaction_id", "customer_id"] + FEATURE_COLUMNS + [TARGET_COLUMN]].copy()
    else:
        output = features[["transaction_id", "customer_id"] + FEATURE_COLUMNS].copy()
    return output.reset_index(drop=True)


def build_training_features(curated_training: pd.DataFrame) -> pd.DataFrame:
    return build_feature_frame(curated_training, include_target=True)


def build_inference_features(curated_inference: pd.DataFrame) -> pd.DataFrame:
    return build_feature_frame(curated_inference, include_target=False)


def assert_feature_contract(training: pd.DataFrame, inference: pd.DataFrame) -> None:
    training_features = [column for column in TRAINING_COLUMNS if column not in {TARGET_COLUMN, "split"}]
    expected_inference = INFERENCE_COLUMNS
    if training_features != expected_inference:
        raise ValueError("Internal feature contract constants are inconsistent.")
    missing_training = [column for column in training_features if column not in training.columns]
    missing_inference = [column for column in expected_inference if column not in inference.columns]
    if missing_training or missing_inference:
        raise ValueError(
            f"Feature contract mismatch. missing_training={missing_training} "
            f"missing_inference={missing_inference}"
        )

