from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .config import FeatureContract


def current_event_time() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_synthetic_source_dataframe(
    rows: int = 24, contract: FeatureContract | None = None
) -> pd.DataFrame:
    contract = contract or FeatureContract.standalone()
    records: list[dict[str, Any]] = []
    event_time = current_event_time()
    for idx in range(rows):
        records.append(
            {
                contract.batch_identifier_column: f"CUST-{idx + 1:04d}",
                "age": 24 + (idx * 5) % 43,
                "income": 32000 + (idx * 3111) % 85000,
                "account_tenure_months": 1 + (idx * 7) % 72,
                "monthly_spend": 40 + (idx * 19) % 380,
                "support_tickets_90d": idx % 5,
                contract.target_column: idx % 2,
                contract.event_time_feature_name: event_time,
            }
        )
    return pd.DataFrame(records)


def transform_raw_record(
    record: dict[str, Any], contract: FeatureContract | None = None
) -> dict[str, Any]:
    contract = contract or FeatureContract.standalone()
    transformed: dict[str, Any] = {
        contract.record_identifier_name: str(
            record.get(contract.record_identifier_name)
            or record.get(contract.batch_identifier_column)
            or record.get(contract.realtime_lookup_key)
        ),
        contract.event_time_feature_name: str(
            record.get(contract.event_time_feature_name) or current_event_time()
        ),
    }
    for name in contract.inference_features:
        transformed[name] = float(record[name])
    if contract.target_column in record:
        transformed[contract.target_column] = int(record[contract.target_column])
    return transformed


def transform_dataframe(
    dataframe: pd.DataFrame, contract: FeatureContract | None = None
) -> pd.DataFrame:
    contract = contract or FeatureContract.standalone()
    records = [
        transform_raw_record(row, contract)
        for row in dataframe.to_dict(orient="records")
    ]
    columns = [
        contract.record_identifier_name,
        contract.event_time_feature_name,
        *contract.inference_features,
    ]
    if contract.target_column in records[0]:
        columns.append(contract.target_column)
    return pd.DataFrame(records)[columns]


def build_feature_store_record(
    record: dict[str, Any], contract: FeatureContract | None = None
) -> list[dict[str, str]]:
    contract = contract or FeatureContract.standalone()
    transformed = transform_raw_record(record, contract)
    ordered_names = [
        contract.record_identifier_name,
        contract.event_time_feature_name,
        *contract.inference_features,
    ]
    if contract.target_column in transformed:
        ordered_names.append(contract.target_column)
    return [
        {"FeatureName": name, "ValueAsString": str(transformed[name])}
        for name in ordered_names
    ]


def build_realtime_payload_from_feature_record(
    record: dict[str, Any],
    record_id: str,
    request_id: str,
    contract: FeatureContract | None = None,
) -> dict[str, Any]:
    contract = contract or FeatureContract.standalone()
    return {
        contract.realtime_lookup_key: record_id,
        "features": {name: float(record[name]) for name in contract.inference_features},
        "request_id": request_id,
    }
