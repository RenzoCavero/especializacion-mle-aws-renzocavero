from __future__ import annotations

import csv
import io
import json
from typing import Any


FEATURE_NAMES = [
    "age",
    "income",
    "account_tenure_months",
    "monthly_spend",
    "support_tickets_90d",
]


def _row_from_mapping(record: dict[str, Any]) -> list[float]:
    features = record.get("features", record)
    return [float(features[name]) for name in FEATURE_NAMES]


def input_fn(request_body: str | bytes, content_type: str = "application/json") -> list[list[float]]:
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    content_type = (content_type or "").split(";")[0].strip().lower()

    if content_type == "application/json":
        payload = json.loads(request_body)
        if isinstance(payload, dict):
            return [_row_from_mapping(payload)]
        if isinstance(payload, list):
            return [_row_from_mapping(item) for item in payload]
        raise ValueError("JSON payload must be an object or list of objects.")

    if content_type in {"text/csv", "application/csv"}:
        rows: list[list[float]] = []
        reader = csv.reader(io.StringIO(request_body))
        for row in reader:
            if not row:
                continue
            if row[0] in {"customer_id", "transaction_id"}:
                continue
            numeric = [float(value) for value in row[-len(FEATURE_NAMES) :]]
            rows.append(numeric)
        return rows

    raise ValueError(f"Unsupported content type: {content_type}")
