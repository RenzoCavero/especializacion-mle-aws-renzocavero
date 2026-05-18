from __future__ import annotations

from typing import Any


REQUIRED_TRANSACTION_FIELDS = [
    "transaction_id",
    "user_id",
    "card_id",
    "merchant_id",
    "device_id",
    "amount",
    "currency",
    "category",
    "channel",
    "location",
    "timestamp",
]


class ValidationError(ValueError):
    pass


def validate_required_fields(payload: dict[str, Any]) -> None:
    missing = [
        field
        for field in REQUIRED_TRANSACTION_FIELDS
        if field not in payload or payload[field] in {None, ""}
    ]
    if missing:
        raise ValidationError("Faltan campos obligatorios: " + ", ".join(missing))


def validate_no_unexpected_model_features(
    feature_names: set[str], allowed_names: set[str]
) -> None:
    unexpected = sorted(feature_names.difference(allowed_names))
    if unexpected:
        raise ValidationError("Features inesperadas en el vector: " + ", ".join(unexpected))

