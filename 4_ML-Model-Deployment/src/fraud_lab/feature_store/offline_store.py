from __future__ import annotations

from typing import Any

from fraud_lab.common.io_utils import read_csv, write_csv
from fraud_lab.common.time_utils import sort_key
from fraud_lab.config import data_dir, ensure_fraud_dirs
from fraud_lab.feature_store.feature_groups import entity_key


class LocalOfflineFeatureStore:
    """Simula SageMaker Feature Store Offline Store con CSV historicos en S3 local."""

    def __init__(self) -> None:
        ensure_fraud_dirs()

    def _path(self, feature_group: str):
        return data_dir() / "feature_store" / "offline" / feature_group / "features.csv"

    def put_records(self, feature_group: str, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        path = self._path(feature_group)
        existing = read_csv(path)
        rows = [*existing, *[{key: str(value) for key, value in record.items()} for record in records]]
        fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys()))
        write_csv(path, rows, fieldnames=fieldnames)

    def replace_records(self, feature_group: str, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        rows = [{key: str(value) for key, value in record.items()} for record in records]
        fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys()))
        write_csv(self._path(feature_group), rows, fieldnames=fieldnames)

    def read_records(self, feature_group: str) -> list[dict[str, str]]:
        return read_csv(self._path(feature_group))

    def latest_as_of(
        self,
        feature_group: str,
        record_id: str,
        transaction_event_time: str,
    ) -> dict[str, Any]:
        key_name = entity_key(feature_group)
        candidates = []
        tx_time = sort_key(transaction_event_time)
        for row in self.read_records(feature_group):
            if row.get(key_name) != str(record_id):
                continue
            event_time = row.get("event_time", "")
            if event_time and sort_key(event_time) <= tx_time:
                candidates.append(row)
        if not candidates:
            return {}
        latest = max(candidates, key=lambda item: sort_key(item["event_time"]))
        return dict(latest)

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
            merged.update(self.latest_as_of(group, str(record_id), cleaned["timestamp"]))
        return merged
