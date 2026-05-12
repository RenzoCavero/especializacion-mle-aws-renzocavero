"""Cleaning functions for raw datasets."""

from __future__ import annotations

from typing import Tuple

import pandas as pd

from src.data_utils import require_columns
from src.schemas import CUSTOMER_COLUMNS, INFERENCE_TRANSACTION_COLUMNS, TRANSACTION_COLUMNS


def _clean_common_transactions(df: pd.DataFrame, known_customers: set[str]) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned = cleaned.drop_duplicates(subset=["transaction_id"], keep="first")
    cleaned["amount"] = pd.to_numeric(cleaned["amount"], errors="coerce")
    median_amount = cleaned.loc[cleaned["amount"] > 0, "amount"].median()
    if pd.isna(median_amount):
        median_amount = 1.0
    cleaned["amount"] = cleaned["amount"].fillna(median_amount)
    cleaned = cleaned[cleaned["amount"] > 0].copy()
    cleaned = cleaned[cleaned["customer_id"].isin(known_customers)].copy()
    cleaned["country"] = cleaned["country"].fillna("UNKNOWN")
    cleaned["merchant_category"] = cleaned["merchant_category"].fillna("unknown")
    cleaned["channel"] = cleaned["channel"].fillna("unknown")
    cleaned["device_type"] = cleaned["device_type"].fillna("unknown")
    cleaned["event_time"] = pd.to_datetime(cleaned["event_time"], errors="coerce", utc=True)
    cleaned = cleaned.dropna(subset=["event_time"])
    cleaned["event_time"] = cleaned["event_time"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    return cleaned.reset_index(drop=True)


def clean_customers(customers: pd.DataFrame) -> pd.DataFrame:
    require_columns(customers, CUSTOMER_COLUMNS, "customers")
    cleaned = customers.copy()
    cleaned = cleaned.drop_duplicates(subset=["customer_id"], keep="first")
    cleaned["region"] = cleaned["region"].fillna("unknown")
    cleaned["segment"] = cleaned["segment"].fillna("retail")
    cleaned["income_band"] = cleaned["income_band"].fillna("medium")
    cleaned["age"] = pd.to_numeric(cleaned["age"], errors="coerce").fillna(cleaned["age"].median())
    cleaned["age"] = cleaned["age"].clip(lower=18, upper=90).astype(int)
    cleaned["risk_score_seed"] = pd.to_numeric(cleaned["risk_score_seed"], errors="coerce").fillna(0.5)
    cleaned["risk_score_seed"] = cleaned["risk_score_seed"].clip(lower=0.0, upper=1.0)
    cleaned["signup_date"] = pd.to_datetime(cleaned["signup_date"], errors="coerce").dt.date.astype("string")
    cleaned = cleaned.dropna(subset=["customer_id", "signup_date"])
    return cleaned[CUSTOMER_COLUMNS].reset_index(drop=True)


def clean_transactions(transactions: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    require_columns(transactions, TRANSACTION_COLUMNS, "transactions")
    known_customers = set(customers["customer_id"].astype(str))
    cleaned = _clean_common_transactions(transactions, known_customers)
    cleaned["is_fraud"] = pd.to_numeric(cleaned["is_fraud"], errors="coerce").fillna(0).astype(int)
    return cleaned[TRANSACTION_COLUMNS].reset_index(drop=True)


def clean_inference_transactions(inference_transactions: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    require_columns(inference_transactions, INFERENCE_TRANSACTION_COLUMNS, "inference_transactions")
    known_customers = set(customers["customer_id"].astype(str))
    cleaned = _clean_common_transactions(inference_transactions, known_customers)
    return cleaned[INFERENCE_TRANSACTION_COLUMNS].reset_index(drop=True)


def clean_all(
    customers: pd.DataFrame,
    transactions: pd.DataFrame,
    inference_transactions: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cleaned_customers = clean_customers(customers)
    cleaned_transactions = clean_transactions(transactions, cleaned_customers)
    cleaned_inference = clean_inference_transactions(inference_transactions, cleaned_customers)
    return cleaned_customers, cleaned_transactions, cleaned_inference

