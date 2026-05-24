from __future__ import annotations

import re
from collections.abc import Iterable


RESOURCE_LIMIT_MARKERS = (
    "ResourceLimitExceeded",
    "service limit",
    "Service Quotas",
    "quota",
    "request an increase",
)


def parse_instance_type_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def unique_instance_types(primary: str, fallbacks: Iterable[str]) -> tuple[str, ...]:
    candidates: list[str] = []
    for item in (primary, *fallbacks):
        if item and item not in candidates:
            candidates.append(item)
    return tuple(candidates)


def is_resource_limit_error(exc: BaseException) -> bool:
    response = getattr(exc, "response", {})
    code = response.get("Error", {}).get("Code") if isinstance(response, dict) else None
    if code == "ResourceLimitExceeded":
        return True
    message = str(exc)
    return any(marker in message for marker in RESOURCE_LIMIT_MARKERS)


def instance_suffix(instance_type: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", instance_type.replace("ml.", "")).strip("-")


def job_name_with_instance(base_name: str, instance_type: str, max_length: int = 63) -> str:
    suffix = f"-{instance_suffix(instance_type)}"
    if len(base_name) + len(suffix) <= max_length:
        return f"{base_name}{suffix}"
    return f"{base_name[: max_length - len(suffix)]}{suffix}"
