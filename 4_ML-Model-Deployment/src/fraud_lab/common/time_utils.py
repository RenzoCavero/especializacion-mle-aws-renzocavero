from __future__ import annotations

from datetime import datetime, timezone


SUPPORTED_FORMATS = (
    "%d/%m/%Y %H:%M",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
)


def parse_timestamp(value: str) -> datetime:
    value = str(value).strip()
    for fmt in SUPPORTED_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Timestamp invalido: {value!r}. Usa dd/mm/yyyy HH:MM o ISO UTC.")


def to_iso_utc(value: str | datetime) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = parse_timestamp(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_request_id() -> str:
    return "REQ-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def hour_of_day(iso_timestamp: str) -> int:
    return parse_timestamp(iso_timestamp).hour


def day_of_week(iso_timestamp: str) -> int:
    return parse_timestamp(iso_timestamp).weekday()


def is_weekend(iso_timestamp: str) -> int:
    return 1 if day_of_week(iso_timestamp) >= 5 else 0


def sort_key(iso_timestamp: str) -> datetime:
    return parse_timestamp(iso_timestamp)

