from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from fraud_lab.config import artifacts_dir, ensure_fraud_dirs


MODEL_NAME = "fraud_model_simulator"
MODEL_VERSION = "fraud_model_v1"
FEATURE_VERSION = "fraud_features_v1"
FEATURE_SET = "fraud_realtime_v1"


CURRENT_TRANSACTION_FEATURES: list[dict[str, Any]] = [
    {"name": "amount_normalized", "type": "float", "default": 0.0},
    {"name": "currency_normalized_amount", "type": "float", "default": 0.0},
    {"name": "hour_of_day", "type": "int", "default": 0},
    {"name": "day_of_week", "type": "int", "default": 0},
    {"name": "is_weekend", "type": "int", "default": 0},
    {"name": "category_electronics", "type": "int", "default": 0},
    {"name": "category_travel", "type": "int", "default": 0},
    {"name": "category_grocery", "type": "int", "default": 0},
    {"name": "channel_mobile", "type": "int", "default": 0},
    {"name": "channel_web", "type": "int", "default": 0},
    {"name": "is_cross_border", "type": "int", "default": 0},
]


ONLINE_STORE_FEATURES: list[dict[str, Any]] = [
    {"name": "account_age_days", "feature_group": "user_profile_features", "entity_key": "user_id", "type": "int", "default": 0},
    {"name": "customer_segment_premium", "feature_group": "user_profile_features", "entity_key": "user_id", "type": "int", "default": 0},
    {"name": "user_txn_count_1h", "feature_group": "user_behavior_features", "entity_key": "user_id", "type": "int", "default": 0},
    {"name": "user_avg_amount_30d", "feature_group": "user_behavior_features", "entity_key": "user_id", "type": "float", "default": 0.0},
    {"name": "card_txn_count_5m", "feature_group": "card_velocity_features", "entity_key": "card_id", "type": "int", "default": 0},
    {"name": "card_declined_count_1h", "feature_group": "card_velocity_features", "entity_key": "card_id", "type": "int", "default": 0},
    {"name": "merchant_fraud_rate_30d", "feature_group": "merchant_risk_features", "entity_key": "merchant_id", "type": "float", "default": 0.0},
    {"name": "merchant_risk_score", "feature_group": "merchant_risk_features", "entity_key": "merchant_id", "type": "float", "default": 0.0},
    {"name": "device_users_count_7d", "feature_group": "device_features", "entity_key": "device_id", "type": "int", "default": 0},
    {"name": "device_trust_score", "feature_group": "device_features", "entity_key": "device_id", "type": "float", "default": 0.0},
]


FEATURE_ORDER = [
    item["name"] for item in CURRENT_TRANSACTION_FEATURES + ONLINE_STORE_FEATURES
]


@dataclass(frozen=True)
class FeatureContract:
    feature_set: str
    model_name: str
    model_version: str
    feature_version: str
    current_transaction_features: list[dict[str, Any]]
    online_store_features: list[dict[str, Any]]
    feature_order: list[str]

    @property
    def defaults(self) -> dict[str, float]:
        values: dict[str, float] = {}
        for item in self.current_transaction_features + self.online_store_features:
            values[item["name"]] = float(item.get("default", 0.0))
        return values


def default_contract() -> FeatureContract:
    return FeatureContract(
        feature_set=FEATURE_SET,
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        feature_version=FEATURE_VERSION,
        current_transaction_features=CURRENT_TRANSACTION_FEATURES,
        online_store_features=ONLINE_STORE_FEATURES,
        feature_order=FEATURE_ORDER,
    )


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value)


def contract_to_yaml(contract: FeatureContract) -> str:
    lines = [
        f"feature_set: {contract.feature_set}",
        f"model_name: {contract.model_name}",
        f"model_version: {contract.model_version}",
        f"feature_version: {contract.feature_version}",
        "",
        "current_transaction_features:",
    ]
    for item in contract.current_transaction_features:
        lines.append(f"  - name: {item['name']}")
        lines.append(f"    type: {item['type']}")
        lines.append(f"    default: {_yaml_scalar(item['default'])}")
    lines.append("")
    lines.append("online_store_features:")
    for item in contract.online_store_features:
        lines.append(f"  - name: {item['name']}")
        lines.append(f"    feature_group: {item['feature_group']}")
        lines.append(f"    entity_key: {item['entity_key']}")
        lines.append(f"    type: {item['type']}")
        lines.append(f"    default: {_yaml_scalar(item['default'])}")
    lines.append("")
    lines.append("feature_order:")
    lines.extend(f"  - {name}" for name in contract.feature_order)
    return "\n".join(lines) + "\n"


def write_default_artifacts() -> dict[str, str]:
    ensure_fraud_dirs()
    contract = default_contract()
    preprocessing_dir = artifacts_dir() / "preprocessing"
    model_dir = artifacts_dir() / "model"
    feature_order_path = preprocessing_dir / "feature_order.json"
    contract_path = preprocessing_dir / "feature_contract.yaml"
    contract_path.write_text(contract_to_yaml(contract), encoding="utf-8")
    feature_order_path.write_text(
        json.dumps(contract.feature_order, indent=2) + "\n", encoding="utf-8"
    )
    (preprocessing_dir / "category_encoder.json").write_text(
        json.dumps({"known_categories": ["electronics", "travel", "grocery"], "handle_unknown": "all_known_columns_zero"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (preprocessing_dir / "channel_encoder.json").write_text(
        json.dumps({"known_channels": ["mobile", "web"], "handle_unknown": "all_known_columns_zero"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (preprocessing_dir / "scaler.json").write_text(
        json.dumps({"amount_normalized": "amount in PEN, no fitted scaler in simulator"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (model_dir / "model_metadata.json").write_text(
        json.dumps(
            {
                "model_name": contract.model_name,
                "model_version": contract.model_version,
                "model_type": "weighted_rule_simulator",
                "endpoint_equivalent": "SageMaker Real-Time Endpoint",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "feature_contract": str(contract_path),
        "feature_order": str(feature_order_path),
    }


def load_feature_order() -> list[str]:
    path = artifacts_dir() / "preprocessing" / "feature_order.json"
    if not path.exists():
        write_default_artifacts()
    return json.loads(path.read_text(encoding="utf-8"))

