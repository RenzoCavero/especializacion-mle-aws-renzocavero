"""Custom Model Quality evaluator for SageMaker Processing.

This script is intentionally standalone because it runs inside a Processing
container. It reads prediction and ground-truth debug JSONL files from S3,
joins them by inference_id, computes model quality metrics, writes a report,
and publishes custom CloudWatch metrics.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import boto3
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score


OUTPUT_DIR = Path("/opt/ml/processing/output")


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    bucket_key = uri[5:]
    bucket, _, key = bucket_key.partition("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI without bucket/key: {uri}")
    return bucket, key.rstrip("/")


def _list_jsonl_objects(s3, uri: str, window_hours: int) -> list[dict[str, Any]]:
    bucket, prefix = _parse_s3_uri(uri)
    paginator = s3.get_paginator("list_objects_v2")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    objects: list[dict[str, Any]] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = str(item.get("Key") or "")
            if not key.endswith(".jsonl"):
                continue
            last_modified = item.get("LastModified")
            if last_modified is None or last_modified >= cutoff:
                objects.append({"bucket": bucket, "key": key, "last_modified": last_modified})
    if objects:
        return sorted(objects, key=lambda item: str(item.get("last_modified") or ""))

    latest: dict[str, Any] | None = None
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = str(item.get("Key") or "")
            if not key.endswith(".jsonl"):
                continue
            if latest is None or item.get("LastModified") > latest.get("last_modified"):
                latest = {"bucket": bucket, "key": key, "last_modified": item.get("LastModified")}
    return [latest] if latest else []


def _read_jsonl_objects(s3, objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in objects:
        response = s3.get_object(Bucket=item["bucket"], Key=item["key"])
        body = response["Body"].read().decode("utf-8")
        for line in body.splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def _compute_metrics(joined: pd.DataFrame) -> dict[str, float | int | None]:
    y_true = joined["label"].astype(int)
    y_pred = joined["prediction"].astype(int)
    metrics: dict[str, float | int | None] = {
        "records_evaluated": int(len(joined)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "auc": None,
    }
    if "probability" in joined.columns and joined["probability"].notna().all() and y_true.nunique() > 1:
        metrics["auc"] = float(roc_auc_score(y_true, joined["probability"].astype(float)))
    return metrics


def _status(metrics: dict[str, float | int | None]) -> dict[str, Any]:
    min_records = int(_env("MODEL_QUALITY_MIN_RECORDS", "20"))
    accuracy_threshold = float(_env("MODEL_QUALITY_ACCURACY_THRESHOLD", "0.75"))
    f1_threshold = float(_env("MODEL_QUALITY_F1_THRESHOLD", "0.70"))
    auc_threshold = float(_env("MODEL_QUALITY_AUC_THRESHOLD", "0.70"))
    records = int(metrics.get("records_evaluated") or 0)
    checks = {
        "min_records": {"value": records, "threshold": min_records, "passed": records >= min_records},
        "accuracy": {
            "value": metrics.get("accuracy"),
            "threshold": accuracy_threshold,
            "passed": float(metrics.get("accuracy") or 0.0) >= accuracy_threshold,
        },
        "f1": {
            "value": metrics.get("f1"),
            "threshold": f1_threshold,
            "passed": float(metrics.get("f1") or 0.0) >= f1_threshold,
        },
        "auc": {
            "value": metrics.get("auc"),
            "threshold": auc_threshold,
            "passed": None
            if metrics.get("auc") is None
            else float(metrics.get("auc") or 0.0) >= auc_threshold,
        },
    }
    required = [checks["min_records"]["passed"], checks["accuracy"]["passed"], checks["f1"]["passed"]]
    if metrics.get("auc") is not None:
        required.append(bool(checks["auc"]["passed"]))
    quality_status = "pass" if all(bool(item) for item in required) else "fail"
    if records < min_records:
        quality_status = "insufficient_data"
    return {"status": quality_status, "checks": checks}


def _publish_metrics(cloudwatch, metrics: dict[str, float | int | None]) -> None:
    namespace = _env("METRIC_NAMESPACE", "MLOps/Lab")
    endpoint_name = _env("ENDPOINT_NAME", "mlops-lab-endpoint")
    metric_data = [
        {
            "MetricName": _env("MODEL_QUALITY_RECORDS_METRIC_NAME", "ModelQualityRecords"),
            "Dimensions": [{"Name": "EndpointName", "Value": endpoint_name}],
            "Value": float(metrics.get("records_evaluated") or 0),
            "Unit": "Count",
        }
    ]
    for key, env_name, default in [
        ("accuracy", "MODEL_QUALITY_ACCURACY_METRIC_NAME", "ModelQualityAccuracy"),
        ("f1", "MODEL_QUALITY_F1_METRIC_NAME", "ModelQualityF1"),
        ("auc", "MODEL_QUALITY_AUC_METRIC_NAME", "ModelQualityAUC"),
    ]:
        value = metrics.get(key)
        if value is None:
            continue
        metric_data.append(
            {
                "MetricName": _env(env_name, default),
                "Dimensions": [{"Name": "EndpointName", "Value": endpoint_name}],
                "Value": float(value),
                "Unit": "None",
            }
        )
    cloudwatch.put_metric_data(Namespace=namespace, MetricData=metric_data)


def main() -> None:
    session = boto3.Session(region_name=_env("AWS_REGION"))
    s3 = session.client("s3")
    cloudwatch = session.client("cloudwatch")
    window_hours = int(_env("CUSTOM_MODEL_QUALITY_WINDOW_HOURS", "24"))
    prediction_objects = _list_jsonl_objects(s3, _env("PREDICTIONS_S3_URI"), window_hours)
    ground_truth_objects = _list_jsonl_objects(s3, _env("GROUND_TRUTH_DEBUG_S3_URI"), window_hours)
    predictions = pd.DataFrame(_read_jsonl_objects(s3, prediction_objects))
    ground_truth = pd.DataFrame(_read_jsonl_objects(s3, ground_truth_objects))
    if predictions.empty or ground_truth.empty:
        raise ValueError("No prediction or ground-truth JSONL records were found for custom Model Quality.")

    joined = predictions.merge(
        ground_truth[["inference_id", "label"]],
        on="inference_id",
        how="inner",
        validate="one_to_one",
    )
    if joined.empty:
        raise ValueError("No joined prediction/ground-truth rows found by inference_id.")

    metrics = _compute_metrics(joined)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "custom_model_quality_processing_job",
        "endpoint_name": _env("ENDPOINT_NAME"),
        "prediction_objects": [f"s3://{item['bucket']}/{item['key']}" for item in prediction_objects],
        "ground_truth_objects": [f"s3://{item['bucket']}/{item['key']}" for item in ground_truth_objects],
        "prediction_records": int(len(predictions)),
        "ground_truth_records": int(len(ground_truth)),
        "joined_records": int(len(joined)),
        "metrics": metrics,
        **_status(metrics),
        "published_metrics": {
            "namespace": _env("METRIC_NAMESPACE", "MLOps/Lab"),
            "dimension": {"EndpointName": _env("ENDPOINT_NAME")},
        },
    }
    _publish_metrics(cloudwatch, metrics)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "model_quality_report.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
