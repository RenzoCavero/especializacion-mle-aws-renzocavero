from __future__ import annotations

from typing import Any

from fraud_lab.common.time_utils import day_of_week, hour_of_day, is_weekend
from fraud_lab.features.encoders import encode_category, encode_channel


def build_current_transaction_features(cleaned: dict[str, Any]) -> tuple[dict[str, float], list[str]]:
    warnings: list[str] = []
    category_features, category_warnings = encode_category(str(cleaned["category"]))
    channel_features, channel_warnings = encode_channel(str(cleaned["channel"]))
    warnings.extend(category_warnings)
    warnings.extend(channel_warnings)

    amount_pen = float(cleaned["amount_pen"])
    features: dict[str, float] = {
        "amount_normalized": amount_pen,
        "currency_normalized_amount": amount_pen,
        "hour_of_day": float(hour_of_day(cleaned["timestamp"])),
        "day_of_week": float(day_of_week(cleaned["timestamp"])),
        "is_weekend": float(is_weekend(cleaned["timestamp"])),
        "is_cross_border": 1.0 if cleaned.get("country") != "PE" else 0.0,
    }
    features.update({key: float(value) for key, value in category_features.items()})
    features.update({key: float(value) for key, value in channel_features.items()})
    return features, warnings

