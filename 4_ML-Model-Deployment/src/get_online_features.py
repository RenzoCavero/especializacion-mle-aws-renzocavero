from __future__ import annotations

import argparse
from typing import Any

from .aws_clients import client_error_code, clients
from .config import (
    ConfigError,
    FeatureContract,
    load_config,
    load_feature_contract,
    read_json,
    utc_now,
    write_json,
)
from .create_feature_store import ensure_feature_store
from .feature_transformations import build_realtime_payload_from_feature_record
from .validate_request_response import example_request, validate_inference_request


def _convert_feature_value(value: str) -> Any:
    if value is None:
        return None
    try:
        if "." in str(value):
            return float(value)
        return int(value)
    except ValueError:
        return value


def standalone_payload(contract: FeatureContract | None = None) -> dict[str, Any]:
    return example_request(contract or FeatureContract.standalone())


def get_online_features(record_id: str | None = None) -> dict[str, Any]:
    config = load_config(require_aws=False)

    if config.lab_mode == "standalone" and config.feature_group_name:
        ensure_feature_store(seed_records=True)
        config = load_config(require_aws=False)

    contract = load_feature_contract(config)

    if not config.feature_group_name:
        payload = standalone_payload(contract)
        payload["request_id"] = f"standalone-{utc_now()}"
        validate_inference_request(payload, contract)
        write_json(config.metadata_path("online_features.json"), payload)
        print("Payload sintetico generado porque FEATURE_GROUP_NAME no esta definido.")
        return payload

    feature_store_metadata = read_json(config.metadata_path("feature_store.json"), default={})
    record_id = (
        record_id
        or config.realtime_record_id
        or feature_store_metadata.get("sample_record_id")
        or "CUST-0001"
    )
    aws_config = load_config(require_aws=True)
    featurestore = clients(aws_config).featurestore_runtime
    try:
        response = featurestore.get_record(
            FeatureGroupName=config.feature_group_name,
            RecordIdentifierValueAsString=record_id,
        )
    except Exception as exc:
        code = client_error_code(exc)
        if code in {"ResourceNotFound", "ValidationException"}:
            raise ConfigError(
                f"No se pudo consultar Feature Group {config.feature_group_name!r}. "
                "Verifica region, nombre y Online Store."
            ) from exc
        raise

    if not response.get("Record"):
        raise ConfigError(f"Online Store no devolvio registros para {record_id!r}.")
    raw_features = {
        item["FeatureName"]: _convert_feature_value(item.get("ValueAsString"))
        for item in response["Record"]
    }
    payload = build_realtime_payload_from_feature_record(
        raw_features,
        record_id=record_id,
        request_id=f"feature-store-{utc_now()}",
        contract=contract,
    )
    validate_inference_request(payload, contract)
    write_json(config.metadata_path("online_features.json"), payload)
    print(f"Features online obtenidas desde {config.feature_group_name}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Obtener features online para inferencia real-time.")
    parser.add_argument("--record-id", default="", help="RecordIdentifierValueAsString para Feature Store.")
    args = parser.parse_args()
    get_online_features(record_id=args.record_id or None)


if __name__ == "__main__":
    main()
