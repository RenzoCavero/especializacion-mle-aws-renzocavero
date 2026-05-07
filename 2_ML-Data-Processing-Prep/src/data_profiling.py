"""Data profiling for raw and prepared datasets."""

from __future__ import annotations

from typing import Dict, Mapping

import pandas as pd

from src.data_utils import json_safe, utc_now_iso


def _numeric_summary(series: pd.Series) -> Dict[str, object]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return {}
    return {
        "min": numeric.min(),
        "max": numeric.max(),
        "mean": numeric.mean(),
        "median": numeric.median(),
        "std": numeric.std(),
        "p95": numeric.quantile(0.95),
    }


def profile_dataframe(df: pd.DataFrame, key_columns: list[str] | None = None) -> Dict[str, object]:
    key_columns = key_columns or []
    profile: Dict[str, object] = {
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": list(df.columns),
        "nulls": df.isna().sum().to_dict(),
        "dtypes": {column: str(dtype) for column, dtype in df.dtypes.items()},
        "duplicate_rows": int(df.duplicated().sum()),
        "numeric_summary": {},
        "categorical_top_values": {},
    }

    duplicate_keys: Dict[str, int] = {}
    for column in key_columns:
        if column in df.columns:
            duplicate_keys[column] = int(df[column].duplicated().sum())
    profile["duplicate_keys"] = duplicate_keys

    numeric_summary: Dict[str, object] = {}
    categorical_top_values: Dict[str, object] = {}
    for column in df.columns:
        if pd.api.types.is_numeric_dtype(df[column]) or column in {"amount", "age", "risk_score_seed"}:
            numeric_summary[column] = _numeric_summary(df[column])
        else:
            top_values = df[column].astype("string").fillna("<NULL>").value_counts().head(5)
            categorical_top_values[column] = top_values.to_dict()

    profile["numeric_summary"] = numeric_summary
    profile["categorical_top_values"] = categorical_top_values
    return json_safe(profile)


def build_profile(datasets: Mapping[str, pd.DataFrame]) -> Dict[str, object]:
    key_columns = {
        "customers": ["customer_id"],
        "transactions": ["transaction_id"],
        "inference_transactions": ["transaction_id"],
        "cleaned_customers": ["customer_id"],
        "cleaned_transactions": ["transaction_id"],
        "features_training": ["transaction_id"],
        "features_inference": ["transaction_id"],
    }
    return {
        "generated_at": utc_now_iso(),
        "datasets": {
            name: profile_dataframe(df, key_columns.get(name, []))
            for name, df in datasets.items()
        },
    }

