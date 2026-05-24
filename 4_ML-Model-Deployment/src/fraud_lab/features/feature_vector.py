from __future__ import annotations

from typing import Any

from fraud_lab.features.feature_contract import FeatureContract, default_contract, load_feature_order
from fraud_lab.schemas import FeatureVector


def assemble_feature_vector(
    cleaned: dict[str, Any],
    current_features: dict[str, float],
    online_features: dict[str, Any],
    contract: FeatureContract | None = None,
    warnings: list[str] | None = None,
) -> FeatureVector:
    contract = contract or default_contract()
    feature_order = load_feature_order()
    defaults = contract.defaults
    assembled: dict[str, float] = {}
    all_warnings = list(warnings or [])

    for name in feature_order:
        if name in current_features:
            assembled[name] = float(current_features[name])
        elif name in online_features and online_features[name] not in {None, ""}:
            assembled[name] = float(online_features[name])
        else:
            assembled[name] = float(defaults.get(name, 0.0))
            all_warnings.append(f"Feature faltante {name}; se aplica default.")

    extra = sorted(set(current_features).difference(feature_order))
    if extra:
        all_warnings.append("Features extra ignoradas: " + ", ".join(extra))

    return FeatureVector(
        transaction_id=str(cleaned["transaction_id"]),
        event_time=str(cleaned["timestamp"]),
        values=assembled,
        ordered_values=[assembled[name] for name in feature_order],
        warnings=all_warnings,
    )
