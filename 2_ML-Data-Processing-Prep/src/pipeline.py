"""Cloud pipeline orchestration for the Glue job."""

from __future__ import annotations

from typing import Any, Dict, Iterable

import pandas as pd

from src.build_inference_dataset import build_inference_dataset
from src.build_training_dataset import build_training_dataset
from src.clean_data import clean_all
from src.data_profiling import build_profile
from src.data_quality import validate_raw_data
from src.data_utils import utc_now_iso
from src.dataset_card import build_dataset_card, dataset_card_to_markdown
from src.feature_engineering import (
    assert_feature_contract,
    build_inference_features,
    build_training_features,
)
from src.glue_catalog import catalog_object_key, register_all_tables
from src.lineage_report import build_lineage, lineage_to_markdown
from src.s3_io import read_csv_from_s3, write_csv_to_s3, write_json_to_s3, write_text_to_s3
from src.transform_data import build_curated_dataset


ALL_STEPS = [
    "catalog",
    "profile",
    "quality",
    "process",
    "features",
    "training-dataset",
    "inference-dataset",
    "lineage",
    "dataset-card",
]


def _write_csv_output(
    s3_client: Any,
    df: pd.DataFrame,
    bucket_name: str,
    key: str,
    table_name: str | None = None,
) -> None:
    write_csv_to_s3(s3_client, df, bucket_name, key)
    if not table_name:
        return
    target_key = catalog_object_key(table_name)
    if target_key == key:
        return
    s3_client.copy_object(
        Bucket=bucket_name,
        CopySource={"Bucket": bucket_name, "Key": key},
        Key=target_key,
    )


def normalize_steps(steps: str | Iterable[str]) -> list[str]:
    if isinstance(steps, str):
        raw = [item.strip() for item in steps.split(",") if item.strip()]
    else:
        raw = [str(item).strip() for item in steps if str(item).strip()]
    if not raw or "all" in raw:
        return ALL_STEPS.copy()
    unknown = [step for step in raw if step not in ALL_STEPS]
    if unknown:
        raise ValueError(f"Unknown pipeline steps: {unknown}. Valid steps: {ALL_STEPS}")
    return raw


def _read_raw(s3_client: Any, bucket_name: str) -> Dict[str, pd.DataFrame]:
    return {
        "customers": read_csv_from_s3(s3_client, bucket_name, "raw/customers.csv"),
        "transactions": read_csv_from_s3(s3_client, bucket_name, "raw/transactions.csv"),
        "inference_transactions": read_csv_from_s3(s3_client, bucket_name, "raw/inference_transactions.csv"),
    }


def _prepare_all(raw: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    customers = raw["customers"]
    transactions = raw["transactions"]
    inference_transactions = raw["inference_transactions"]
    quality = validate_raw_data(customers, transactions, inference_transactions)
    if not quality["summary"]["pipeline_can_continue"]:  # type: ignore[index]
        raise ValueError("Data quality ERROR rules failed. See quality report for details.")

    cleaned_customers, cleaned_transactions, cleaned_inference = clean_all(
        customers,
        transactions,
        inference_transactions,
    )
    curated_training = build_curated_dataset(cleaned_transactions, cleaned_customers, include_target=True)
    curated_inference = build_curated_dataset(cleaned_inference, cleaned_customers, include_target=False)
    training_features = build_training_features(curated_training)
    inference_features = build_inference_features(curated_inference)
    training_dataset = build_training_dataset(training_features)
    inference_dataset = build_inference_dataset(inference_features)
    assert_feature_contract(training_dataset, inference_dataset)

    profile = build_profile(
        {
            **raw,
            "cleaned_customers": cleaned_customers,
            "cleaned_transactions": cleaned_transactions,
            "features_training": training_dataset,
            "features_inference": inference_dataset,
        }
    )
    return {
        "quality": quality,
        "profile": profile,
        "cleaned_customers": cleaned_customers,
        "cleaned_transactions": cleaned_transactions,
        "cleaned_inference_transactions": cleaned_inference,
        "curated_training": curated_training,
        "curated_inference": curated_inference,
        "training_features": training_features,
        "inference_features": inference_features,
        "training_dataset": training_dataset,
        "inference_dataset": inference_dataset,
    }


def run_pipeline(
    s3_client: Any,
    glue_client: Any,
    bucket_name: str,
    database_name: str,
    resource_prefix: str,
    steps: str,
    run_id: str,
) -> Dict[str, object]:
    selected_steps = normalize_steps(steps)
    print(f"Starting pipeline run_id={run_id} bucket={bucket_name} steps={selected_steps}")
    raw = _read_raw(s3_client, bucket_name)
    prepared = _prepare_all(raw)

    outputs: Dict[str, object] = {
        "run_id": run_id,
        "started_at": utc_now_iso(),
        "steps": selected_steps,
        "bucket": bucket_name,
        "database": database_name,
    }

    if "catalog" in selected_steps:
        registered_tables = register_all_tables(glue_client, database_name, bucket_name)
        outputs["registered_tables"] = registered_tables
        print(f"Registered Glue tables: {registered_tables}")

    if "profile" in selected_steps:
        write_json_to_s3(s3_client, prepared["profile"], bucket_name, "profiles/profile.json")
        print("Wrote profiles/profile.json")

    if "quality" in selected_steps:
        write_json_to_s3(s3_client, prepared["quality"], bucket_name, "quality/quality_report.json")
        print("Wrote quality/quality_report.json")

    if "process" in selected_steps:
        _write_csv_output(
            s3_client,
            prepared["cleaned_customers"],
            bucket_name,
            "cleaned/customers.csv",
            "cleaned_customers",
        )
        _write_csv_output(
            s3_client,
            prepared["cleaned_transactions"],
            bucket_name,
            "cleaned/transactions.csv",
            "cleaned_transactions",
        )
        write_csv_to_s3(
            s3_client,
            prepared["cleaned_inference_transactions"],
            bucket_name,
            "cleaned/inference_transactions.csv",
        )
        _write_csv_output(
            s3_client,
            prepared["curated_training"],
            bucket_name,
            "curated/customer_transactions.csv",
            "curated_customer_transactions",
        )
        write_csv_to_s3(
            s3_client,
            prepared["curated_inference"],
            bucket_name,
            "curated/inference_customer_transactions.csv",
        )
        print("Wrote cleaned/ and curated/ datasets")

    if "features" in selected_steps:
        write_csv_to_s3(s3_client, prepared["training_features"], bucket_name, "features/training_features.csv")
        write_csv_to_s3(s3_client, prepared["inference_features"], bucket_name, "features/inference_features.csv")
        print("Wrote features/training_features.csv and features/inference_features.csv")

    if "training-dataset" in selected_steps:
        _write_csv_output(
            s3_client,
            prepared["training_dataset"],
            bucket_name,
            "features/training_dataset.csv",
            "features_training",
        )
        print("Wrote features/training_dataset.csv")

    if "inference-dataset" in selected_steps:
        _write_csv_output(
            s3_client,
            prepared["inference_dataset"],
            bucket_name,
            "inference/inference_dataset.csv",
            "features_inference",
        )
        print("Wrote inference/inference_dataset.csv")

    lineage = build_lineage(bucket_name, database_name, resource_prefix)
    if "lineage" in selected_steps:
        write_json_to_s3(s3_client, lineage, bucket_name, "lineage/lineage.json")
        write_text_to_s3(
            s3_client,
            lineage_to_markdown(lineage),
            bucket_name,
            "lineage/lineage.md",
            "text/markdown",
        )
        print("Wrote lineage reports")

    if "dataset-card" in selected_steps:
        card = build_dataset_card(
            bucket_name=bucket_name,
            profile=prepared["profile"],
            quality=prepared["quality"],
            training_rows=len(prepared["training_dataset"]),
            inference_rows=len(prepared["inference_dataset"]),
        )
        write_json_to_s3(s3_client, card, bucket_name, "reports/dataset_card.json")
        write_text_to_s3(
            s3_client,
            dataset_card_to_markdown(card),
            bucket_name,
            "reports/dataset_card.md",
            "text/markdown",
        )
        print("Wrote dataset card")

    outputs["finished_at"] = utc_now_iso()
    write_json_to_s3(s3_client, outputs, bucket_name, "logs/pipeline_run.json")
    print("Pipeline finished successfully")
    return outputs
