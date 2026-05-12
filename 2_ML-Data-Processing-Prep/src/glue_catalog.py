"""Glue Data Catalog registration for lab datasets."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


def _string_columns(names: list[str]) -> List[Dict[str, str]]:
    return [{"Name": name, "Type": "string"} for name in names]


TABLES: Dict[str, Dict[str, object]] = {
    "raw_customers": {
        "prefix": "raw/customers.csv",
        "columns": [
            {"Name": "customer_id", "Type": "string"},
            {"Name": "signup_date", "Type": "string"},
            {"Name": "segment", "Type": "string"},
            {"Name": "region", "Type": "string"},
            {"Name": "age", "Type": "int"},
            {"Name": "income_band", "Type": "string"},
            {"Name": "risk_score_seed", "Type": "double"},
        ],
    },
    "raw_transactions": {
        "prefix": "raw/transactions.csv",
        "columns": [
            {"Name": "transaction_id", "Type": "string"},
            {"Name": "customer_id", "Type": "string"},
            {"Name": "event_time", "Type": "string"},
            {"Name": "amount", "Type": "double"},
            {"Name": "merchant_category", "Type": "string"},
            {"Name": "channel", "Type": "string"},
            {"Name": "country", "Type": "string"},
            {"Name": "device_type", "Type": "string"},
            {"Name": "is_fraud", "Type": "int"},
        ],
    },
    "raw_inference_transactions": {
        "prefix": "raw/inference_transactions.csv",
        "columns": [
            {"Name": "transaction_id", "Type": "string"},
            {"Name": "customer_id", "Type": "string"},
            {"Name": "event_time", "Type": "string"},
            {"Name": "amount", "Type": "double"},
            {"Name": "merchant_category", "Type": "string"},
            {"Name": "channel", "Type": "string"},
            {"Name": "country", "Type": "string"},
            {"Name": "device_type", "Type": "string"},
        ],
    },
    "cleaned_customers": {
        "prefix": "cleaned/customers.csv",
        "columns": _string_columns(["customer_id", "signup_date", "segment", "region", "income_band"])
        + [{"Name": "age", "Type": "int"}, {"Name": "risk_score_seed", "Type": "double"}],
    },
    "cleaned_transactions": {
        "prefix": "cleaned/transactions.csv",
        "columns": [
            {"Name": "transaction_id", "Type": "string"},
            {"Name": "customer_id", "Type": "string"},
            {"Name": "event_time", "Type": "string"},
            {"Name": "amount", "Type": "double"},
            {"Name": "merchant_category", "Type": "string"},
            {"Name": "channel", "Type": "string"},
            {"Name": "country", "Type": "string"},
            {"Name": "device_type", "Type": "string"},
            {"Name": "is_fraud", "Type": "int"},
        ],
    },
    "curated_customer_transactions": {
        "prefix": "curated/customer_transactions.csv",
        "columns": _string_columns(
            [
                "transaction_id",
                "customer_id",
                "event_time",
                "merchant_category",
                "channel",
                "country",
                "device_type",
                "signup_date",
                "segment",
                "region",
                "income_band",
            ]
        )
        + [
            {"Name": "amount", "Type": "double"},
            {"Name": "age", "Type": "int"},
            {"Name": "risk_score_seed", "Type": "double"},
            {"Name": "customer_tenure_days", "Type": "int"},
            {"Name": "event_hour", "Type": "int"},
            {"Name": "event_dayofweek", "Type": "int"},
            {"Name": "is_weekend", "Type": "int"},
            {"Name": "is_night", "Type": "int"},
            {"Name": "amount_log", "Type": "double"},
            {"Name": "is_fraud", "Type": "int"},
        ],
    },
    "features_training": {
        "prefix": "features/training_dataset.csv",
        "columns": _string_columns(["transaction_id", "customer_id"])
        + [
            {"Name": "amount", "Type": "double"},
            {"Name": "amount_log", "Type": "double"},
            {"Name": "age", "Type": "double"},
            {"Name": "risk_score_seed", "Type": "double"},
            {"Name": "customer_tenure_days", "Type": "double"},
            {"Name": "event_hour", "Type": "double"},
            {"Name": "event_dayofweek", "Type": "double"},
            {"Name": "is_weekend", "Type": "double"},
            {"Name": "is_night", "Type": "double"},
            {"Name": "customer_txn_count", "Type": "double"},
            {"Name": "customer_avg_amount", "Type": "double"},
            {"Name": "customer_max_amount", "Type": "double"},
            {"Name": "amount_to_customer_avg", "Type": "double"},
            {"Name": "high_risk_country", "Type": "double"},
            {"Name": "channel_atm", "Type": "double"},
            {"Name": "channel_card_present", "Type": "double"},
            {"Name": "channel_mobile", "Type": "double"},
            {"Name": "channel_online", "Type": "double"},
            {"Name": "channel_wire", "Type": "double"},
            {"Name": "segment_premium", "Type": "double"},
            {"Name": "segment_retail", "Type": "double"},
            {"Name": "segment_smb", "Type": "double"},
            {"Name": "merchant_electronics", "Type": "double"},
            {"Name": "merchant_fuel", "Type": "double"},
            {"Name": "merchant_grocery", "Type": "double"},
            {"Name": "merchant_travel", "Type": "double"},
            {"Name": "merchant_utilities", "Type": "double"},
            {"Name": "is_fraud", "Type": "int"},
            {"Name": "split", "Type": "string"},
        ],
    },
    "features_inference": {
        "prefix": "inference/inference_dataset.csv",
        "columns": _string_columns(["transaction_id", "customer_id"])
        + [
            {"Name": "amount", "Type": "double"},
            {"Name": "amount_log", "Type": "double"},
            {"Name": "age", "Type": "double"},
            {"Name": "risk_score_seed", "Type": "double"},
            {"Name": "customer_tenure_days", "Type": "double"},
            {"Name": "event_hour", "Type": "double"},
            {"Name": "event_dayofweek", "Type": "double"},
            {"Name": "is_weekend", "Type": "double"},
            {"Name": "is_night", "Type": "double"},
            {"Name": "customer_txn_count", "Type": "double"},
            {"Name": "customer_avg_amount", "Type": "double"},
            {"Name": "customer_max_amount", "Type": "double"},
            {"Name": "amount_to_customer_avg", "Type": "double"},
            {"Name": "high_risk_country", "Type": "double"},
            {"Name": "channel_atm", "Type": "double"},
            {"Name": "channel_card_present", "Type": "double"},
            {"Name": "channel_mobile", "Type": "double"},
            {"Name": "channel_online", "Type": "double"},
            {"Name": "channel_wire", "Type": "double"},
            {"Name": "segment_premium", "Type": "double"},
            {"Name": "segment_retail", "Type": "double"},
            {"Name": "segment_smb", "Type": "double"},
            {"Name": "merchant_electronics", "Type": "double"},
            {"Name": "merchant_fuel", "Type": "double"},
            {"Name": "merchant_grocery", "Type": "double"},
            {"Name": "merchant_travel", "Type": "double"},
            {"Name": "merchant_utilities", "Type": "double"},
        ],
    },
}


def source_key(table_name: str) -> str:
    return str(TABLES[table_name]["prefix"])


def catalog_prefix(table_name: str) -> str:
    definition = TABLES[table_name]
    explicit_prefix = definition.get("catalog_prefix")
    if explicit_prefix:
        return str(explicit_prefix).strip("/")
    key = source_key(table_name).strip("/")
    if key.endswith(".csv"):
        return key[:-4]
    return key


def catalog_object_key(table_name: str) -> str:
    key = source_key(table_name).strip("/")
    filename = key.rsplit("/", 1)[-1]
    return f"{catalog_prefix(table_name)}/{filename}"


def catalog_location(table_name: str, bucket_name: str) -> str:
    return f"s3://{bucket_name}/{catalog_prefix(table_name)}/"


def _is_missing_s3_object(exc: Exception) -> bool:
    response = getattr(exc, "response", {})
    error = response.get("Error", {}) if isinstance(response, dict) else {}
    code = str(error.get("Code", ""))
    return code in {"404", "NoSuchKey", "NotFound"}


def sync_catalog_data(s3_client: Any, bucket_name: str, table_names: Iterable[str] | None = None) -> list[str]:
    """Copy single-file lab outputs into folder-style prefixes used by Athena."""
    synced_keys: list[str] = []
    for table_name in table_names or TABLES:
        key = source_key(table_name)
        target_key = catalog_object_key(table_name)
        if key == target_key:
            continue
        try:
            s3_client.head_object(Bucket=bucket_name, Key=key)
        except Exception as exc:
            if _is_missing_s3_object(exc):
                continue
            raise
        s3_client.copy_object(
            Bucket=bucket_name,
            CopySource={"Bucket": bucket_name, "Key": key},
            Key=target_key,
        )
        synced_keys.append(target_key)
    return synced_keys


def table_input(table_name: str, bucket_name: str) -> Dict[str, object]:
    definition = TABLES[table_name]
    location = catalog_location(table_name, bucket_name)
    return {
        "Name": table_name,
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {
            "classification": "csv",
            "skip.header.line.count": "1",
            "compressionType": "none",
            "typeOfData": "file",
        },
        "StorageDescriptor": {
            "Columns": definition["columns"],
            "Location": location,
            "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
            "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
            "SerdeInfo": {
                "SerializationLibrary": "org.apache.hadoop.hive.serde2.OpenCSVSerde",
                "Parameters": {
                    "separatorChar": ",",
                    "quoteChar": '"',
                    "escapeChar": "\\",
                },
            },
        },
    }


def upsert_table(glue_client: Any, database_name: str, table_name: str, bucket_name: str) -> None:
    payload = table_input(table_name, bucket_name)
    try:
        glue_client.get_table(DatabaseName=database_name, Name=table_name)
    except glue_client.exceptions.EntityNotFoundException:
        glue_client.create_table(DatabaseName=database_name, TableInput=payload)
    else:
        glue_client.update_table(DatabaseName=database_name, TableInput=payload)


def register_all_tables(glue_client: Any, database_name: str, bucket_name: str) -> list[str]:
    registered = []
    for table_name in TABLES:
        upsert_table(glue_client, database_name, table_name, bucket_name)
        registered.append(table_name)
    return registered
