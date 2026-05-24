from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .aws_clients import client_error_code, clients
from .config import (
    ConfigError,
    FeatureContract,
    LOCAL_CACHE_DIR,
    ROOT_DIR,
    load_config,
    parse_s3_uri,
    save_feature_contract,
    timestamp_slug,
    utc_now,
    write_json,
)
from .create_feature_store import ensure_feature_store
from .feature_transformations import generate_synthetic_source_dataframe, transform_dataframe


def generate_synthetic_dataframe(rows: int = 24, contract: FeatureContract | None = None) -> pd.DataFrame:
    contract = contract or FeatureContract.standalone()
    return transform_dataframe(generate_synthetic_source_dataframe(rows, contract), contract)


def validate_batch_dataframe(df: pd.DataFrame, contract: FeatureContract) -> None:
    required = [contract.batch_identifier_column, *contract.inference_features]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ConfigError("Faltan columnas para batch input: " + ", ".join(missing))
    if contract.target_column in contract.inference_features:
        raise ConfigError("target_column no puede estar en inference_features.")


def build_batch_payload(df: pd.DataFrame, contract: FeatureContract) -> tuple[pd.DataFrame, pd.DataFrame]:
    validate_batch_dataframe(df, contract)
    manifest = pd.DataFrame(
        {
            "row_index": range(len(df)),
            contract.batch_identifier_column: df[contract.batch_identifier_column].astype(str),
        }
    )
    payload = df[contract.inference_features].copy()
    if contract.target_column in payload.columns:
        raise ConfigError("El batch payload no debe contener target column.")
    return payload, manifest


def _download_json_contract(s3_client: Any, uri: str) -> FeatureContract:
    bucket, key = parse_s3_uri(uri)
    local_path = LOCAL_CACHE_DIR / "feature_contract_integrated.json"
    s3_client.download_file(bucket, key, str(local_path))
    raw = json.loads(local_path.read_text(encoding="utf-8"))
    contract = FeatureContract.from_mapping(raw)
    save_feature_contract(contract)
    return contract


def _find_csv_in_s3_prefix(s3_client: Any, uri: str) -> str:
    bucket, key = parse_s3_uri(uri)
    if key.endswith(".csv"):
        return uri
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=key.rstrip("/") + "/")
    for item in response.get("Contents", []):
        if item["Key"].endswith(".csv"):
            return f"s3://{bucket}/{item['Key']}"
    raise ConfigError(
        "OFFLINE_STORE_S3_URI no contiene un CSV legible por este laboratorio. "
        "Exporta una consulta del Offline Store a CSV o usa standalone_mode."
    )


def _download_integrated_dataframe(s3_client: Any, uri: str) -> pd.DataFrame:
    csv_uri = _find_csv_in_s3_prefix(s3_client, uri)
    bucket, key = parse_s3_uri(csv_uri)
    local_path = LOCAL_CACHE_DIR / "integrated_offline_store_sample.csv"
    s3_client.download_file(bucket, key, str(local_path))
    return pd.read_csv(local_path)


def _download_dataframe_from_s3_uri(s3_client: Any, uri: str, local_name: str) -> pd.DataFrame:
    bucket, key = parse_s3_uri(uri)
    local_path = LOCAL_CACHE_DIR / local_name
    s3_client.download_file(bucket, key, str(local_path))
    return pd.read_csv(local_path)


def prepare_batch_input() -> dict[str, Any]:
    config = load_config(require_aws=True)
    aws = clients(config)
    s3 = aws.s3
    feature_store_metadata: dict[str, Any] = {}

    should_prepare_feature_store = config.lab_mode == "standalone" or not (
        config.offline_store_s3_uri and config.feature_contract_s3_uri
    )
    if should_prepare_feature_store:
        feature_store_metadata = ensure_feature_store(seed_records=True)

    if feature_store_metadata:
        contract = FeatureContract.from_mapping(
            read_json(LOCAL_CACHE_DIR / "feature_contract.json")
        )
    elif config.lab_mode == "integrated" and config.feature_contract_s3_uri:
        contract = _download_json_contract(s3, config.feature_contract_s3_uri)
    else:
        contract = FeatureContract.standalone()
        save_feature_contract(contract)

    if feature_store_metadata.get("offline_export_s3_uri"):
        dataframe = _download_dataframe_from_s3_uri(
            s3,
            feature_store_metadata["offline_export_s3_uri"],
            "feature_store_offline_export_for_batch.csv",
        )
        source = feature_store_metadata["offline_export_s3_uri"]
    elif config.lab_mode == "integrated" and config.offline_store_s3_uri:
        dataframe = _download_integrated_dataframe(s3, config.offline_store_s3_uri)
        source = config.offline_store_s3_uri
    else:
        dataframe = generate_synthetic_dataframe(contract=contract)
        source = "synthetic_standalone_dataset_without_feature_store"

    payload, manifest = build_batch_payload(dataframe, contract)
    run_id = timestamp_slug()
    local_input_with_ids = LOCAL_CACHE_DIR / "batch_input_with_ids.csv"
    local_payload = LOCAL_CACHE_DIR / "batch_input.csv"
    local_manifest = LOCAL_CACHE_DIR / "batch_manifest.csv"
    dataframe.to_csv(local_input_with_ids, index=False)
    payload.to_csv(local_payload, index=False, header=False)
    manifest.to_csv(local_manifest, index=False)

    s3_key = "/".join([config.s3_prefix.strip("/"), "batch", "input", run_id, "batch_input.csv"])
    s3.upload_file(str(local_payload), config.s3_bucket_name, s3_key)
    batch_input_s3_uri = f"s3://{config.s3_bucket_name}/{s3_key}"

    metadata = {
        "lab_mode": config.lab_mode,
        "source": source,
        "feature_group_name": feature_store_metadata.get("feature_group_name", config.feature_group_name),
        "offline_store_s3_uri": feature_store_metadata.get(
            "offline_store_s3_uri", config.offline_store_s3_uri
        ),
        "offline_export_s3_uri": feature_store_metadata.get("offline_export_s3_uri", ""),
        "transformation_script": feature_store_metadata.get(
            "transformation_script", "src/feature_transformations.py"
        ),
        "batch_input_s3_uri": batch_input_s3_uri,
        "local_payload": str(local_payload.relative_to(ROOT_DIR)),
        "local_manifest": str(local_manifest.relative_to(ROOT_DIR)),
        "local_input_with_ids": str(local_input_with_ids.relative_to(ROOT_DIR)),
        "record_count": len(payload),
        "inference_features": contract.inference_features,
        "batch_identifier_column": contract.batch_identifier_column,
        "target_column_excluded": contract.target_column not in payload.columns,
        "prepared_at": utc_now(),
    }
    write_json(config.metadata_path("batch_input.json"), metadata)
    print(f"Batch input subido a {batch_input_s3_uri}")
    return metadata


def main() -> None:
    argparse.ArgumentParser(description="Preparar batch input para SageMaker Batch Transform.").parse_args()
    try:
        prepare_batch_input()
    except Exception as exc:
        if client_error_code(exc) in {"AccessDenied", "AccessDeniedException"}:
            raise SystemExit("Permisos insuficientes para preparar batch input en S3.") from exc
        raise


if __name__ == "__main__":
    main()
