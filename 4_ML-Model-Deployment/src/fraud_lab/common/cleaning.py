from __future__ import annotations

from typing import Any

from .normalization import (
    amount_to_pen,
    normalize_category,
    normalize_channel,
    normalize_currency,
    parse_amount,
    parse_location,
)
from .time_utils import to_iso_utc
from .validation import validate_required_fields


def clean_transaction(raw: dict[str, Any]) -> dict[str, Any]:
    validate_required_fields(raw)
    amount = parse_amount(raw["amount"])
    currency = normalize_currency(raw["currency"])
    city, country = parse_location(raw["location"])
    cleaned = {
        "transaction_id": str(raw["transaction_id"]),
        "user_id": str(raw["user_id"]),
        "card_id": str(raw["card_id"]),
        "merchant_id": str(raw["merchant_id"]),
        "device_id": str(raw["device_id"]),
        "amount": amount,
        "currency": currency,
        "amount_pen": amount_to_pen(amount, currency),
        "category": normalize_category(raw["category"]),
        "channel": normalize_channel(raw["channel"]),
        "city": city,
        "country": country,
        "timestamp": to_iso_utc(str(raw["timestamp"])),
    }
    if "source_channel" in raw:
        cleaned["source_channel"] = str(raw["source_channel"])
    return cleaned

