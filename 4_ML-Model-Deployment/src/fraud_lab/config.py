from __future__ import annotations

import os
from pathlib import Path


def root_dir() -> Path:
    override = os.getenv("FRAUD_LAB_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return root_dir() / "data"


def artifacts_dir() -> Path:
    return root_dir() / "artifacts"


def path(*parts: str) -> Path:
    return root_dir().joinpath(*parts)


def ensure_fraud_dirs() -> None:
    directories = [
        data_dir() / "lake" / "raw",
        data_dir() / "lake" / "cleaned",
        data_dir() / "lake" / "curated",
        data_dir() / "feature_store" / "online",
        data_dir() / "feature_store" / "offline",
        data_dir() / "operational" / "decisions",
        data_dir() / "operational" / "inference_logs" / "raw_events",
        data_dir() / "operational" / "inference_logs" / "cleaned_events",
        data_dir() / "operational" / "inference_logs" / "feature_vectors",
        data_dir() / "operational" / "inference_logs" / "predictions",
        data_dir() / "events" / "pending",
        data_dir() / "events" / "processed",
        data_dir() / "batch" / "predictions",
        data_dir() / "batch" / "model_ready",
        data_dir() / "retraining",
        artifacts_dir() / "model",
        artifacts_dir() / "preprocessing",
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def default_online_transaction() -> dict[str, str]:
    return {
        "transaction_id": "T001",
        "user_id": "U123",
        "card_id": "C789",
        "merchant_id": "M999",
        "device_id": "D123",
        "amount": "500",
        "currency": "pen",
        "category": "Electronics",
        "channel": "Mobile",
        "location": "Lima|PE",
        "timestamp": "17/05/2026 14:20",
    }


def should_write_last_seen_features() -> bool:
    value = os.getenv("FRAUD_WRITE_LAST_SEEN_FEATURES", "false")
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}

