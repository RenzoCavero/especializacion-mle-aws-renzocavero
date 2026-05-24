"""Smoke test contract for deployment pipeline."""

from __future__ import annotations


def validate_smoke_response(response: object) -> bool:
    if not isinstance(response, list) or not response:
        return False
    first = response[0]
    return isinstance(first, dict) and "prediction" in first and "probability" in first

