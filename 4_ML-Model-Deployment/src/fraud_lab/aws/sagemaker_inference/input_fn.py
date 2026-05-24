from __future__ import annotations

import csv
import io
import json
from typing import Any


FEATURE_ORDER = [
    "amount_normalized",
    "currency_normalized_amount",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "category_electronics",
    "category_travel",
    "category_grocery",
    "channel_mobile",
    "channel_web",
    "is_cross_border",
    "account_age_days",
    "customer_segment_premium",
    "user_txn_count_1h",
    "user_avg_amount_30d",
    "card_txn_count_5m",
    "card_declined_count_1h",
    "merchant_fraud_rate_30d",
    "merchant_risk_score",
    "device_users_count_7d",
    "device_trust_score",
]


def _row_from_mapping(record: dict[str, Any]) -> list[float]:
    if "ordered_values" in record:
        return [float(value) for value in record["ordered_values"]]
    features = record.get("features", record)
    return [float(features.get(name, 0.0)) for name in FEATURE_ORDER]


def input_fn(request_body: str | bytes, content_type: str = "application/json") -> list[list[float]]:
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    normalized_type = (content_type or "").split(";")[0].strip().lower()

    if normalized_type == "application/json":
        payload = json.loads(request_body)
        if isinstance(payload, dict):
            return [_row_from_mapping(payload)]
        if isinstance(payload, list):
            return [_row_from_mapping(item) for item in payload]
        raise ValueError("JSON payload must be an object or a list of objects.")

    if normalized_type in {"text/csv", "application/csv"}:
        rows: list[list[float]] = []
        reader = csv.reader(io.StringIO(request_body))
        for row in reader:
            if not row:
                continue
            if row[0] in {"transaction_id", "customer_id"}:
                continue
            rows.append([float(value) for value in row[-len(FEATURE_ORDER) :]])
        return rows

    raise ValueError(f"Unsupported content type: {content_type}")

