from __future__ import annotations

import json
import time
from typing import Any

from src.aws_clients import client_error_code
from src.config import ConfigError

from fraud_lab.aws.clients import FraudAwsClients
from fraud_lab.aws.config import FraudAwsConfig, load_fraud_aws_config
from fraud_lab.aws.s3_data_lake import S3DataLake
from fraud_lab.common.time_utils import sort_key
from fraud_lab.feature_store.feature_groups import FEATURE_GROUPS, entity_key, feature_names
from fraud_lab.feature_store.seed_feature_store import baseline_feature_records
from fraud_lab.features.feature_contract import (
    contract_to_yaml,
    default_contract,
)

STRING_FEATURES = {
    "event_time",
    "last_transaction_country",
    "last_transaction_timestamp",
    "last_channel_used",
    "last_merchant_id",
    "last_device_id",
}


def _feature_type(name: str) -> str:
    if name in STRING_FEATURES or name.endswith("_id"):
        return "String"
    if (
        name.endswith("_count")
        or "_count_" in name
        or name.endswith("_days")
        or name.startswith("is_")
        or name.startswith("kyc_")
        or name.startswith("customer_segment_")
        or name.startswith("device_type_")
    ):
        return "Integral"
    return "Fractional"


def _parse_feature_value(value: str) -> Any:
    if value == "":
        return value
    try:
        number = float(value)
    except ValueError:
        return value
    if number.is_integer():
        return int(number)
    return number


class AwsFeatureStore:
    """SageMaker Feature Store con Online Store y Offline Store en S3."""

    def __init__(
        self,
        config: FraudAwsConfig | None = None,
        clients: FraudAwsClients | None = None,
        s3_lake: S3DataLake | None = None,
    ) -> None:
        self.config = config or load_fraud_aws_config()
        self.clients = clients or FraudAwsClients(self.config)
        self.sagemaker = self.clients.sagemaker
        self.runtime = self.clients.featurestore_runtime
        self.s3_lake = s3_lake or S3DataLake(self.config, self.clients)

    def physical_name(self, logical_group: str) -> str:
        return self.config.physical_feature_group_name(logical_group)

    def _feature_definitions(self, logical_group: str) -> list[dict[str, str]]:
        key_name = entity_key(logical_group)
        names = [key_name, "event_time", *feature_names(logical_group)]
        unique_names = list(dict.fromkeys(names))
        return [
            {"FeatureName": name, "FeatureType": _feature_type(name)}
            for name in unique_names
        ]

    def describe(self, logical_group: str) -> dict[str, Any] | None:
        try:
            return self.sagemaker.describe_feature_group(
                FeatureGroupName=self.physical_name(logical_group)
            )
        except Exception as exc:
            if client_error_code(exc) in {"ResourceNotFound", "ValidationException"}:
                return None
            raise

    def create_feature_group(self, logical_group: str) -> str:
        existing = self.describe(logical_group)
        if existing:
            status = existing.get("FeatureGroupStatus")
            if status == "Created":
                return str(existing["FeatureGroupName"])
            if status in {"CreateFailed", "DeleteFailed"}:
                self.delete_feature_group(logical_group)
                self.wait_until_deleted(logical_group)
            else:
                return self.wait_until_created(logical_group)
        offline_uri = self.config.s3_uri(
            "feature-store",
            "offline-store",
            logical_group,
        )
        self.sagemaker.create_feature_group(
            FeatureGroupName=self.physical_name(logical_group),
            RecordIdentifierFeatureName=entity_key(logical_group),
            EventTimeFeatureName="event_time",
            FeatureDefinitions=self._feature_definitions(logical_group),
            OnlineStoreConfig={"EnableOnlineStore": True},
            OfflineStoreConfig={
                "S3StorageConfig": {"S3Uri": offline_uri},
                "DisableGlueTableCreation": False,
            },
            RoleArn=self.config.sagemaker_execution_role_arn,
            Tags=self.config.tags,
        )
        return self.wait_until_created(logical_group)

    def delete_feature_group(self, logical_group: str) -> None:
        try:
            self.sagemaker.delete_feature_group(
                FeatureGroupName=self.physical_name(logical_group)
            )
        except Exception as exc:
            if client_error_code(exc) in {"ResourceNotFound", "ValidationException"}:
                return
            raise

    def wait_until_deleted(self, logical_group: str, timeout_seconds: int = 600) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if not self.describe(logical_group):
                return
            time.sleep(10)
        raise TimeoutError(f"Timeout esperando eliminacion de Feature Group {logical_group}.")

    def wait_until_created(self, logical_group: str, timeout_seconds: int = 600) -> str:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            description = self.describe(logical_group)
            if not description:
                time.sleep(10)
                continue
            status = description.get("FeatureGroupStatus")
            if status == "Created":
                return str(description["FeatureGroupName"])
            if status in {"CreateFailed", "DeleteFailed"}:
                reason = description.get("FailureReason", "sin detalle")
                raise ConfigError(
                    f"Feature Group {logical_group} fallo con estado {status}: {reason}"
                )
            time.sleep(10)
        raise TimeoutError(f"Timeout esperando Feature Group {logical_group}.")

    def create_all_feature_groups(self) -> dict[str, str]:
        return {
            logical_group: self.create_feature_group(logical_group)
            for logical_group in FEATURE_GROUPS
        }

    def _record_for_put(self, logical_group: str, record: dict[str, Any]) -> list[dict[str, str]]:
        key_name = entity_key(logical_group)
        allowed = {key_name, "event_time", *feature_names(logical_group)}
        missing = [name for name in (key_name, "event_time") if not record.get(name)]
        if missing:
            raise ValueError(
                f"Record para {logical_group} debe incluir: {', '.join(missing)}"
            )
        return [
            {"FeatureName": key, "ValueAsString": str(value)}
            for key, value in record.items()
            if key in allowed and value is not None
        ]

    def put_record(
        self,
        logical_group: str,
        record: dict[str, Any],
        *,
        target_stores: list[str] | None = None,
    ) -> None:
        self.runtime.put_record(
            FeatureGroupName=self.physical_name(logical_group),
            Record=self._record_for_put(logical_group, record),
            TargetStores=target_stores or ["OnlineStore", "OfflineStore"],
        )

    def get_record(self, logical_group: str, record_id: str) -> dict[str, Any]:
        try:
            response = self.runtime.get_record(
                FeatureGroupName=self.physical_name(logical_group),
                RecordIdentifierValueAsString=str(record_id),
            )
        except Exception as exc:
            if client_error_code(exc) in {"ResourceNotFound", "ValidationException"}:
                return {}
            raise
        values: dict[str, Any] = {}
        for item in response.get("Record", []):
            values[item["FeatureName"]] = _parse_feature_value(item.get("ValueAsString", ""))
        return values

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

    def offline_export_key(self, logical_group: str) -> tuple[str, ...]:
        return ("feature-store", "offline-export", logical_group, "features.csv")

    def replace_offline_export(self, logical_group: str, records: list[dict[str, Any]]) -> str:
        if not records:
            return self.s3_lake.put_csv(self.offline_export_key(logical_group), [])
        fieldnames = list(dict.fromkeys(key for row in records for key in row.keys()))
        return self.s3_lake.put_csv(
            self.offline_export_key(logical_group),
            records,
            fieldnames=fieldnames,
        )

    def append_offline_export(self, logical_group: str, records: list[dict[str, Any]]) -> str:
        existing = self.read_offline_export(logical_group)
        rows = [*existing, *[{key: str(value) for key, value in row.items()} for row in records]]
        fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys()))
        return self.s3_lake.put_csv(
            self.offline_export_key(logical_group),
            rows,
            fieldnames=fieldnames,
        )

    def read_offline_export(self, logical_group: str) -> list[dict[str, str]]:
        return self.s3_lake.read_csv(*self.offline_export_key(logical_group))

    def latest_as_of(
        self,
        logical_group: str,
        record_id: str,
        transaction_event_time: str,
    ) -> dict[str, Any]:
        key_name = entity_key(logical_group)
        candidates = []
        tx_time = sort_key(transaction_event_time)
        for row in self.read_offline_export(logical_group):
            if row.get(key_name) != str(record_id):
                continue
            event_time = row.get("event_time", "")
            if event_time and sort_key(event_time) <= tx_time:
                candidates.append(row)
        if not candidates:
            return {}
        latest = max(candidates, key=lambda item: sort_key(item["event_time"]))
        return dict(latest)

    def get_many_offline_for_transaction(self, cleaned: dict[str, Any]) -> dict[str, Any]:
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

    def upload_contract_artifacts(self) -> dict[str, str]:
        contract = default_contract()
        return {
            "feature_contract": self.s3_lake.put_text(
                ("artifacts", "preprocessing", "feature_contract.yaml"),
                contract_to_yaml(contract),
                "text/yaml",
            ),
            "feature_order": self.s3_lake.put_text(
                ("artifacts", "preprocessing", "feature_order.json"),
                json.dumps(contract.feature_order, indent=2) + "\n",
                "application/json",
            ),
        }

    def seed_feature_store(self) -> dict[str, Any]:
        physical_groups = self.create_all_feature_groups()
        counts: dict[str, int] = {}
        for logical_group, records in baseline_feature_records().items():
            latest_by_entity: dict[str, dict[str, Any]] = {}
            key_name = entity_key(logical_group)
            for record in records:
                self.put_record(logical_group, record)
                latest_by_entity[str(record[key_name])] = record
            self.replace_offline_export(logical_group, records)
            counts[logical_group] = len(records)
        artifacts = self.upload_contract_artifacts()
        return {
            "physical_feature_groups": physical_groups,
            "record_counts": counts,
            "offline_exports_prefix": self.config.s3_uri("feature-store", "offline-export"),
            "artifacts": artifacts,
        }
