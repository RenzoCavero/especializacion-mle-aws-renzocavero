from __future__ import annotations

from typing import Any

from fraud_lab.common.io_utils import append_jsonl, write_json
from fraud_lab.config import data_dir, ensure_fraud_dirs


def persist_inference_trace(
    raw_event: dict[str, Any],
    cleaned_event: dict[str, Any],
    feature_vector: dict[str, Any],
    prediction_event: dict[str, Any],
) -> None:
    ensure_fraud_dirs()
    transaction_id = str(raw_event["transaction_id"])
    base = data_dir() / "operational" / "inference_logs"
    write_json(base / "raw_events" / f"{transaction_id}.json", raw_event)
    write_json(base / "cleaned_events" / f"{transaction_id}.json", cleaned_event)
    write_json(base / "feature_vectors" / f"{transaction_id}.json", feature_vector)
    write_json(base / "predictions" / f"{transaction_id}.json", prediction_event)
    append_jsonl(base / "predictions.jsonl", prediction_event)


def persist_decision(decision: dict[str, Any]) -> None:
    transaction_id = str(decision["transaction_id"])
    write_json(data_dir() / "operational" / "decisions" / f"{transaction_id}.json", decision)

