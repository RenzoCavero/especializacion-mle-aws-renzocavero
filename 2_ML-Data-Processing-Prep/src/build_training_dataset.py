"""Build supervised training dataset."""

from __future__ import annotations

import hashlib

import pandas as pd

from src.schemas import TRAINING_COLUMNS


def _split_for_transaction(transaction_id: str) -> str:
    digest = hashlib.sha1(transaction_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "validation"
    return "test"


def build_training_dataset(training_features: pd.DataFrame) -> pd.DataFrame:
    dataset = training_features.copy()
    dataset["split"] = dataset["transaction_id"].astype(str).apply(_split_for_transaction)
    return dataset[TRAINING_COLUMNS].reset_index(drop=True)

