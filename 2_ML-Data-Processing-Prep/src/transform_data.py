"""Curated dataset transformations."""

from __future__ import annotations

import math

import pandas as pd

from src.schemas import CURATED_COLUMNS, TARGET_COLUMN


def build_curated_dataset(transactions: pd.DataFrame, customers: pd.DataFrame, include_target: bool) -> pd.DataFrame:
    curated = transactions.merge(customers, on="customer_id", how="inner")
    event_time = pd.to_datetime(curated["event_time"], errors="coerce", utc=True)
    signup_date = pd.to_datetime(curated["signup_date"], errors="coerce", utc=True)

    curated["customer_tenure_days"] = (event_time.dt.normalize() - signup_date.dt.normalize()).dt.days
    curated["customer_tenure_days"] = curated["customer_tenure_days"].fillna(0).clip(lower=0).astype(int)
    curated["event_hour"] = event_time.dt.hour.fillna(0).astype(int)
    curated["event_dayofweek"] = event_time.dt.dayofweek.fillna(0).astype(int)
    curated["is_weekend"] = curated["event_dayofweek"].isin([5, 6]).astype(int)
    curated["is_night"] = curated["event_hour"].between(0, 5).astype(int)
    curated["amount"] = pd.to_numeric(curated["amount"], errors="coerce").fillna(0.0)
    curated["amount_log"] = curated["amount"].apply(lambda value: math.log1p(max(float(value), 0.0)))

    output_columns = CURATED_COLUMNS + ([TARGET_COLUMN] if include_target else [])
    return curated[output_columns].reset_index(drop=True)

