from __future__ import annotations

import argparse
import time
from typing import Any

from .aws_clients import client_error_code, clients
from .config import (
    ConfigError,
    FeatureContract,
    LOCAL_CACHE_DIR,
    ROOT_DIR,
    load_config,
    parse_s3_uri,
    read_json,
    save_feature_contract,
    timestamp_slug,
    utc_now,
    write_json,
)
from .feature_transformations import (
    build_feature_store_record,
    generate_synthetic_source_dataframe,
    transform_dataframe,
)


def standalone_contract(config) -> FeatureContract:
    contract = FeatureContract.standalone()
    contract.feature_group_name = config.feature_group_name
    contract.offline_store_s3_uri = (
        config.offline_store_s3_uri
        or config.s3_uri("feature-store", "offline-store", contract.feature_group_name)
    )
    contract.model_package_group_name = config.model_package_group_name
    contract.model_artifact_s3_uri = config.model_artifact_s3_uri
    return contract


def _feature_definitions(contract: FeatureContract) -> list[dict[str, str]]:
    definitions = [
        {"FeatureName": contract.record_identifier_name, "FeatureType": "String"},
        {"FeatureName": contract.event_time_feature_name, "FeatureType": "String"},
    ]
    definitions.extend(
        {"FeatureName": name, "FeatureType": "Fractional"}
        for name in contract.inference_features
    )
    definitions.append({"FeatureName": contract.target_column, "FeatureType": "Integral"})
    return definitions


def _offline_store_config(config, contract: FeatureContract) -> dict[str, Any]:
    s3_storage_config: dict[str, str] = {"S3Uri": contract.offline_store_s3_uri}
    if config.kms_key_id:
        s3_storage_config["KmsKeyId"] = config.kms_key_id
    return {
        "S3StorageConfig": s3_storage_config,
        "DisableGlueTableCreation": True,
    }


def _online_store_config(config) -> dict[str, Any]:
    online_config: dict[str, Any] = {"EnableOnlineStore": True, "StorageType": "Standard"}
    if config.kms_key_id:
        online_config["SecurityConfig"] = {"KmsKeyId": config.kms_key_id}
    return online_config


def _describe_feature_group(sagemaker: Any, feature_group_name: str) -> dict[str, Any] | None:
    try:
        return sagemaker.describe_feature_group(FeatureGroupName=feature_group_name)
    except Exception as exc:
        if client_error_code(exc) in {"ResourceNotFound", "ValidationException"}:
            return None
        raise


def _wait_for_feature_group(sagemaker: Any, feature_group_name: str) -> dict[str, Any]:
    for _ in range(60):
        description = _describe_feature_group(sagemaker, feature_group_name)
        if not description:
            time.sleep(10)
            continue
        status = description.get("FeatureGroupStatus")
        if status == "Created":
            return description
        if status in {"CreateFailed", "DeleteFailed"}:
            reason = description.get("FailureReason", "sin detalle")
            raise ConfigError(f"Feature Group {feature_group_name} fallo: {reason}")
        time.sleep(10)
    raise ConfigError(
        f"Feature Group {feature_group_name} no llego a estado Created dentro del tiempo esperado."
    )


def _upload_contract(config, s3: Any, contract: FeatureContract) -> str:
    local_contract = save_feature_contract(contract)
    s3_uri = config.s3_uri("feature-store", "contracts", "feature_contract.json")
    bucket, key = parse_s3_uri(s3_uri)
    s3.upload_file(str(local_contract), bucket, key)
    return s3_uri


def _seed_standalone_records(config, featurestore_runtime: Any, s3: Any, contract: FeatureContract) -> dict[str, Any]:
    raw_dataframe = generate_synthetic_source_dataframe(rows=24, contract=contract)
    feature_dataframe = transform_dataframe(raw_dataframe, contract)

    local_raw = LOCAL_CACHE_DIR / "feature_store_raw_source.csv"
    local_offline_export = LOCAL_CACHE_DIR / "feature_store_offline_export.csv"
    raw_dataframe.to_csv(local_raw, index=False)
    feature_dataframe.to_csv(local_offline_export, index=False)

    run_id = timestamp_slug()
    export_s3_uri = config.s3_uri("feature-store", "offline-export", run_id, "feature_records.csv")
    bucket, key = parse_s3_uri(export_s3_uri)
    s3.upload_file(str(local_offline_export), bucket, key)

    seeded = 0
    for record in feature_dataframe.to_dict(orient="records"):
        featurestore_runtime.put_record(
            FeatureGroupName=contract.feature_group_name,
            Record=build_feature_store_record(record, contract),
            TargetStores=["OnlineStore", "OfflineStore"],
        )
        seeded += 1

    sample_record_id = str(feature_dataframe.iloc[0][contract.record_identifier_name])
    return {
        "record_count": len(feature_dataframe),
        "online_records_seeded": seeded,
        "sample_record_id": sample_record_id,
        "offline_export_s3_uri": export_s3_uri,
        "local_raw_source": str(local_raw.relative_to(ROOT_DIR)),
        "local_offline_export": str(local_offline_export.relative_to(ROOT_DIR)),
    }


def ensure_feature_store(seed_records: bool = True) -> dict[str, Any]:
    config = load_config(require_aws=True)
    if not config.feature_group_name:
        raise ConfigError(
            "FEATURE_GROUP_NAME no esta definido. En standalone_mode el lab genera "
            "un nombre por defecto; revisa RESOURCE_PREFIX y CREATE_STANDALONE_FEATURE_GROUP."
        )

    aws = clients(config)
    sagemaker = aws.sagemaker
    featurestore_runtime = aws.featurestore_runtime
    s3 = aws.s3
    contract = standalone_contract(config)
    contract_s3_uri = _upload_contract(config, s3, contract)
    previous_metadata = read_json(config.metadata_path("feature_store.json"), default={})

    description = _describe_feature_group(sagemaker, contract.feature_group_name)
    created_by_lab = bool(previous_metadata.get("created_by_lab", False))
    if description is None:
        sagemaker.create_feature_group(
            FeatureGroupName=contract.feature_group_name,
            RecordIdentifierFeatureName=contract.record_identifier_name,
            EventTimeFeatureName=contract.event_time_feature_name,
            FeatureDefinitions=_feature_definitions(contract),
            OnlineStoreConfig=_online_store_config(config),
            OfflineStoreConfig=_offline_store_config(config, contract),
            RoleArn=config.sagemaker_execution_role_arn,
            Description="Lab 04 Feature Group with Online Store and Offline Store.",
            Tags=config.tags,
        )
        created_by_lab = True
        description = _wait_for_feature_group(sagemaker, contract.feature_group_name)
    elif description.get("FeatureGroupStatus") != "Created":
        description = _wait_for_feature_group(sagemaker, contract.feature_group_name)

    seed_metadata: dict[str, Any] = {
        key: previous_metadata[key]
        for key in (
            "record_count",
            "online_records_seeded",
            "sample_record_id",
            "offline_export_s3_uri",
            "local_raw_source",
            "local_offline_export",
        )
        if key in previous_metadata
    }
    should_seed = (
        seed_records
        and (config.lab_mode == "standalone" or created_by_lab)
        and not previous_metadata.get("online_records_seeded")
    )
    if should_seed:
        seed_metadata = _seed_standalone_records(config, featurestore_runtime, s3, contract)

    metadata = {
        "feature_group_name": contract.feature_group_name,
        "feature_group_arn": description.get("FeatureGroupArn"),
        "feature_group_status": description.get("FeatureGroupStatus"),
        "created_by_lab": created_by_lab,
        "online_store_enabled": description.get("OnlineStoreConfig", {}).get("EnableOnlineStore", True),
        "offline_store_s3_uri": contract.offline_store_s3_uri,
        "feature_contract_s3_uri": contract_s3_uri,
        "transformation_script": "src/feature_transformations.py",
        "seeded_at": utc_now() if should_seed else previous_metadata.get("seeded_at", ""),
        **seed_metadata,
    }
    write_json(config.metadata_path("feature_store.json"), metadata)
    print(f"Feature Store listo: {contract.feature_group_name}")
    if seed_metadata:
        print(f"Offline export S3: {seed_metadata['offline_export_s3_uri']}")
        print(f"Online sample record: {seed_metadata['sample_record_id']}")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear o reutilizar Feature Store para inferencia.")
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Crear/reutilizar Feature Group sin cargar registros sinteticos.",
    )
    args = parser.parse_args()
    try:
        ensure_feature_store(seed_records=not args.no_seed)
    except Exception as exc:
        if client_error_code(exc) in {"AccessDenied", "AccessDeniedException"}:
            raise SystemExit(
                "Permisos insuficientes para crear o cargar Feature Store. "
                "Revisa sagemaker:CreateFeatureGroup, sagemaker:PutRecord, IAM PassRole y S3."
            ) from exc
        raise


if __name__ == "__main__":
    main()
