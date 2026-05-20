from __future__ import annotations

from typing import Any


def check_required_feature_vector_values(feature_vector: dict[str, Any]) -> list[str]:
    warnings = []
    for name, value in feature_vector.items():
        if value in {None, ""}:
            warnings.append(f"Feature {name} viene vacia.")
    return warnings

