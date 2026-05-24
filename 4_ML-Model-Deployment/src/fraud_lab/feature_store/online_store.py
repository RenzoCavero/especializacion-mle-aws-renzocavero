from __future__ import annotations

from typing import Any

from fraud_lab.common.io_utils import read_json, write_json
from fraud_lab.config import data_dir, ensure_fraud_dirs
from fraud_lab.feature_store.feature_groups import entity_key


class LocalOnlineFeatureStore:
    """Simula SageMaker Feature Store Online Store con un JSON por feature group."""

    def __init__(self) -> None:
        ensure_fraud_dirs()

    def _path(self, feature_group: str):
        return data_dir() / "feature_store" / "online" / f"{feature_group}.json"

    def get_record(self, feature_group: str, record_id: str) -> dict[str, Any]:
        records = read_json(self._path(feature_group), default={})
        return dict(records.get(str(record_id), {}))

    def put_record(self, feature_group: str, record: dict[str, Any]) -> None:
        key_name = entity_key(feature_group)
        if key_name not in record:
            raise ValueError(f"Record para {feature_group} debe incluir {key_name}.")
        path = self._path(feature_group)
        records = read_json(path, default={})
        records[str(record[key_name])] = dict(record)
        write_json(path, records)

    def get_many_for_transaction(self, cleaned: dict[str, Any]) -> dict[str, Any]:
        lookups = {
            "user_profile_features": cleaned["user_id"],
            "user_behavior_features": cleaned["user_id"],
            "card_velocity_features": cleaned["card_id"],
            "merchant_risk_features": cleaned["merchant_id"],
            "device_features": cleaned["device_id"],
        }
        merged: dict[str, Any] = {}
        for group, record_id in lookups.items():
            merged.update(self.get_record(group, str(record_id)))
        return merged

