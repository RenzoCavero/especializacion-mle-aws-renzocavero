"""Prepare raw synthetic fraud data into train/test and batch feature files."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config import (
    BATCH_INPUT_PATH,
    CATEGORICAL_FEATURES,
    DATA_PROFILE_PATH,
    FEATURE_COLUMNS,
    FEATURE_SCHEMA_PATH,
    ID_COLUMNS,
    NUMERIC_FEATURES,
    RAW_BATCH_INPUT_PATH,
    RAW_DATA_DIR,
    RAW_TRANSACTIONS_PATH,
    REQUIRED_RAW_COLUMNS,
    REQUIRED_TRAINING_COLUMNS,
    TARGET_COLUMN,
    TEST_DATA_PATH,
    TEST_SIZE,
    TRAIN_DATA_PATH,
    ensure_directories,
    require_file,
    project_relative,
)
from src.modeling import save_json, utc_now_iso


def validate_columns(df: pd.DataFrame, required_columns: list[str], dataset_name: str) -> None:
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"{dataset_name} is missing required columns: {missing}")


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create deterministic features from raw transaction fields."""

    validate_columns(df, REQUIRED_RAW_COLUMNS, "input dataframe")
    prepared = df.copy()

    numeric_raw = [
        "amount",
        "hour",
        "day_of_week",
        "customer_age_days",
        "transactions_last_24h",
        "avg_amount_30d",
        "chargeback_rate_90d",
        "distance_from_home_km",
        "is_foreign_transaction",
        "is_high_risk_merchant",
    ]
    for column in numeric_raw:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")

    prepared["amount"] = prepared["amount"].clip(lower=0.0)
    prepared["avg_amount_30d"] = prepared["avg_amount_30d"].clip(lower=1.0)
    prepared["amount_log"] = np.log1p(prepared["amount"])
    prepared["amount_to_avg_ratio"] = prepared["amount"] / prepared["avg_amount_30d"].replace(0, 1.0)
    prepared["is_night"] = ((prepared["hour"] <= 5) | (prepared["hour"] >= 23)).astype(int)
    prepared["velocity_amount_score"] = (
        np.log1p(prepared["transactions_last_24h"]) * prepared["amount_to_avg_ratio"]
    )

    for column in CATEGORICAL_FEATURES:
        prepared[column] = prepared[column].fillna("unknown").astype(str).str.lower()

    output_columns = ID_COLUMNS + FEATURE_COLUMNS
    if TARGET_COLUMN in prepared.columns:
        prepared[TARGET_COLUMN] = pd.to_numeric(prepared[TARGET_COLUMN], errors="coerce").fillna(0).astype(int)
        output_columns.append(TARGET_COLUMN)

    return prepared[output_columns]


def ensure_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Return a dataframe with engineered feature columns.

    The input may already be prepared or may still be raw transaction data.
    """

    if all(column in df.columns for column in FEATURE_COLUMNS):
        output_columns = [column for column in ID_COLUMNS if column in df.columns] + FEATURE_COLUMNS
        if TARGET_COLUMN in df.columns:
            output_columns.append(TARGET_COLUMN)
        return df[output_columns].copy()
    return build_features(df)


def stratified_split(
    df: pd.DataFrame,
    target_column: str = TARGET_COLUMN,
    test_size: float = TEST_SIZE,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    train_indices: list[int] = []
    test_indices: list[int] = []

    for label in sorted(df[target_column].unique()):
        label_indices = df.index[df[target_column] == label].to_numpy().copy()
        rng.shuffle(label_indices)
        n_test = max(1, int(round(len(label_indices) * test_size)))
        test_indices.extend(label_indices[:n_test].tolist())
        train_indices.extend(label_indices[n_test:].tolist())

    train_df = df.loc[train_indices].sample(frac=1.0, random_state=seed).reset_index(drop=True)
    test_df = df.loc[test_indices].sample(frac=1.0, random_state=seed + 1).reset_index(drop=True)
    return train_df, test_df


def _numeric_profile(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    profile = {}
    for column in NUMERIC_FEATURES:
        values = pd.to_numeric(df[column], errors="coerce")
        profile[column] = {
            "mean": float(values.mean()),
            "std": float(values.std(ddof=0)),
            "min": float(values.min()),
            "max": float(values.max()),
            "missing": int(values.isna().sum()),
        }
    return profile


def _categorical_profile(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    profile = {}
    for column in CATEGORICAL_FEATURES:
        counts = df[column].fillna("unknown").astype(str).value_counts().to_dict()
        profile[column] = {
            "unique": int(len(counts)),
            "top_values": {str(key): int(value) for key, value in list(counts.items())[:10]},
        }
    return profile


def prepare_data(
    raw_path=RAW_TRANSACTIONS_PATH,
    raw_batch_path=RAW_BATCH_INPUT_PATH,
    train_path=TRAIN_DATA_PATH,
    test_path=TEST_DATA_PATH,
    batch_path=BATCH_INPUT_PATH,
    profile_path=DATA_PROFILE_PATH,
    schema_path=FEATURE_SCHEMA_PATH,
    seed: int = 42,
) -> dict[str, Any]:
    ensure_directories()
    require_file(raw_path, "Run `make data` or `python -m src.generate_dataset` first.")
    require_file(raw_batch_path, "Run `make data` or `python -m src.generate_dataset` first.")

    raw_df = pd.read_csv(raw_path)
    validate_columns(raw_df, REQUIRED_TRAINING_COLUMNS, "raw transactions")
    prepared_df = build_features(raw_df)
    train_df, test_df = stratified_split(prepared_df, seed=seed)

    raw_batch_df = pd.read_csv(raw_batch_path)
    validate_columns(raw_batch_df, REQUIRED_RAW_COLUMNS, "raw batch input")
    batch_df = build_features(raw_batch_df)
    if TARGET_COLUMN in batch_df.columns:
        batch_df = batch_df.drop(columns=[TARGET_COLUMN])

    train_path.parent.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(train_path, index=False)
    test_df.to_csv(test_path, index=False)
    batch_df.to_csv(batch_path, index=False)

    profile = {
        "created_at": utc_now_iso(),
        "source_path": project_relative(Path(raw_path)),
        "raw_rows": int(len(raw_df)),
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "batch_rows": int(len(batch_df)),
        "target_column": TARGET_COLUMN,
        "fraud_rate_raw": float(prepared_df[TARGET_COLUMN].mean()),
        "fraud_rate_train": float(train_df[TARGET_COLUMN].mean()),
        "fraud_rate_test": float(test_df[TARGET_COLUMN].mean()),
        "numeric_profile": _numeric_profile(train_df),
        "categorical_profile": _categorical_profile(train_df),
    }
    save_json(Path(profile_path), profile)

    schema = {
        "created_at": utc_now_iso(),
        "id_columns": ID_COLUMNS,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "target_column": TARGET_COLUMN,
    }
    save_json(Path(schema_path), schema)
    print(f"[prepare] wrote {train_path} rows={len(train_df)}")
    print(f"[prepare] wrote {test_path} rows={len(test_df)}")
    print(f"[prepare] wrote {batch_path} rows={len(batch_df)}")
    return profile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare train/test and batch feature files.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--raw-path", default=str(RAW_TRANSACTIONS_PATH))
    parser.add_argument("--raw-batch-path", default=str(RAW_BATCH_INPUT_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepare_data(
        raw_path=Path(args.raw_path),
        raw_batch_path=Path(args.raw_batch_path),
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
