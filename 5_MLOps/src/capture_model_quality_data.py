"""Invoke the endpoint with inference IDs and store predictions plus ground truth."""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata
from .generate_sample_data import FEATURE_COLUMNS, LABEL_COLUMN, _make_frame
from .simulate_traffic import _load_records


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    bucket_key = uri[5:]
    bucket, _, key = bucket_key.partition("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI without bucket/key: {uri}")
    return bucket, key.rstrip("/")


def _put_jsonl(clients, uri: str, records: list[dict[str, Any]]) -> str:
    bucket, key = _parse_s3_uri(uri)
    body = "".join(json.dumps(record, default=str) + "\n" for record in records).encode("utf-8")
    clients.s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/jsonlines")
    return uri


def _write_local_jsonl(path: Path, records: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, default=str) + "\n")
    return str(path)


def _ground_truth_file(config, traffic_type: str) -> Path:
    if traffic_type == "normal":
        return config.local_cache_dir / "inference_normal_ground_truth.jsonl"
    return config.local_cache_dir / "inference_drift_ground_truth.jsonl"


def _read_ground_truth_jsonl(path: Path) -> dict[str, int]:
    labels: dict[str, int] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            labels[str(row["record_id"])] = int(row[LABEL_COLUMN])
    return labels


def _ground_truth_lookup(config, traffic_type: str) -> dict[str, int]:
    ground_truth_path = _ground_truth_file(config, traffic_type)
    if ground_truth_path.exists():
        return _read_ground_truth_jsonl(ground_truth_path)

    if traffic_type == "normal":
        train_path = config.local_cache_dir / "churn_train.csv"
        if not train_path.exists():
            raise FileNotFoundError("Missing churn_train.csv. Run step 02 before model quality monitoring.")
        frame = pd.read_csv(train_path)
    else:
        metadata = read_metadata(config, "data_generation")
        drift_records = int(metadata.get("drift_records") or 300)
        frame = _make_frame(n_rows=drift_records, seed=49, drift=True)

    if "record_id" not in frame.columns or LABEL_COLUMN not in frame.columns:
        raise ValueError(f"Ground truth source must contain record_id and {LABEL_COLUMN}.")
    return {str(row["record_id"]): int(row[LABEL_COLUMN]) for row in frame.to_dict(orient="records")}


def _traffic_path(config, traffic_type: str) -> Path:
    if traffic_type == "normal":
        return config.local_cache_dir / "inference_normal.jsonl"
    return config.local_cache_dir / "inference_drift.jsonl"


def _parse_prediction(body: str) -> tuple[int, float | None, Any]:
    parsed = json.loads(body)
    first = parsed[0] if isinstance(parsed, list) and parsed else parsed
    if not isinstance(first, dict) or "prediction" not in first:
        raise ValueError(f"Unexpected endpoint response for model quality monitoring: {body}")
    prediction = int(first["prediction"])
    probability = first.get("probability")
    return prediction, float(probability) if probability is not None else None, parsed


def _resolve_label(source_label: int, prediction: int, label_mode: str) -> int:
    if label_mode == "invert-source":
        return 1 - int(source_label)
    if label_mode == "opposite-prediction":
        return 1 - int(prediction)
    return int(source_label)


def capture_model_quality_data(
    traffic_type: str = "normal",
    limit: int = 50,
    sleep_seconds: float = 0.0,
    label_mode: str = "source",
) -> dict[str, object]:
    if traffic_type not in {"normal", "drift"}:
        raise ValueError("--traffic-type must be normal or drift")
    if label_mode not in {"source", "invert-source", "opposite-prediction"}:
        raise ValueError("--label-mode must be source, invert-source, or opposite-prediction")
    if limit <= 0:
        raise ValueError("--limit must be greater than 0")

    config = load_config(validate=True)
    clients = create_clients(config)
    path = _traffic_path(config, traffic_type)
    if not path.exists():
        raise FileNotFoundError(f"Traffic data not found at {path}. Run step 02 first.")

    records = _load_records(path, limit)
    labels = _ground_truth_lookup(config, traffic_type)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    s3_timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d/%H%M%S")
    native_ground_truth_partition = datetime.now(timezone.utc).strftime("%Y/%m/%d/%H")

    prediction_records: list[dict[str, Any]] = []
    ground_truth_records: list[dict[str, Any]] = []
    sagemaker_ground_truth_records: list[dict[str, Any]] = []

    for index, record in enumerate(records):
        record_id = str(record.get("record_id") or f"{traffic_type}-{index:05d}")
        if record_id not in labels:
            raise ValueError(f"No ground truth label found for record_id={record_id}.")
        features = {key: record[key] for key in ["record_id", *FEATURE_COLUMNS] if key in record}
        inference_id = f"{run_id}-{record_id}-{uuid.uuid4().hex[:8]}"
        response = clients.sagemaker_runtime.invoke_endpoint(
            EndpointName=config.endpoint_name,
            Body=json.dumps(features),
            ContentType="application/json",
            Accept="application/json",
            InferenceId=inference_id,
        )
        raw_body = response["Body"].read().decode("utf-8")
        prediction, probability, parsed_response = _parse_prediction(raw_body)
        event_time = datetime.now(timezone.utc).isoformat()
        prediction_records.append(
            {
                "inference_id": inference_id,
                "record_id": record_id,
                "endpoint_name": config.endpoint_name,
                "traffic_type": traffic_type,
                "prediction": prediction,
                "probability": probability,
                "event_time": event_time,
                "raw_response": parsed_response,
            }
        )
        source_label = int(labels[record_id])
        label = _resolve_label(source_label, prediction, label_mode)
        ground_truth_records.append(
            {
                "inference_id": inference_id,
                "record_id": record_id,
                "endpoint_name": config.endpoint_name,
                "traffic_type": traffic_type,
                "label": label,
                "source_label": source_label,
                "label_mode": label_mode,
                "label_name": LABEL_COLUMN,
                "event_time": event_time,
            }
        )
        sagemaker_ground_truth_records.append(
            {
                "groundTruthData": {"data": str(label), "encoding": "CSV"},
                "eventMetadata": {"eventId": inference_id},
                "eventVersion": "0",
            }
        )
        if sleep_seconds:
            import time

            time.sleep(sleep_seconds)

    predictions_s3_uri = f"{config.model_quality_predictions_s3_uri}/{s3_timestamp}/predictions.jsonl"
    ground_truth_debug_s3_uri = f"{config.model_quality_ground_truth_debug_s3_uri}/{s3_timestamp}/ground_truth_debug.jsonl"
    sagemaker_ground_truth_s3_uri = (
        f"{config.model_quality_ground_truth_s3_uri}/"
        f"{native_ground_truth_partition}/ground_truth_{run_id}.jsonl"
    )
    _put_jsonl(clients, predictions_s3_uri, prediction_records)
    _put_jsonl(clients, ground_truth_debug_s3_uri, ground_truth_records)
    _put_jsonl(clients, sagemaker_ground_truth_s3_uri, sagemaker_ground_truth_records)

    local_predictions = _write_local_jsonl(config.local_outputs_dir / "model_quality_predictions.jsonl", prediction_records)
    local_ground_truth = _write_local_jsonl(config.local_outputs_dir / "model_quality_ground_truth.jsonl", ground_truth_records)

    payload = {
        "endpoint_name": config.endpoint_name,
        "traffic_type": traffic_type,
        "label_mode": label_mode,
        "records_sent": len(prediction_records),
        "capture_endpoint_output": config.capture_endpoint_output,
        "inference_id_used": True,
        "predictions_s3_uri": predictions_s3_uri,
        "ground_truth_debug_s3_uri": ground_truth_debug_s3_uri,
        "ground_truth_s3_uri": sagemaker_ground_truth_s3_uri,
        "ground_truth_s3_prefix": config.model_quality_ground_truth_s3_uri,
        "ground_truth_s3_partition": f"{config.model_quality_ground_truth_s3_uri}/{native_ground_truth_partition}",
        "sagemaker_ground_truth_s3_uri": sagemaker_ground_truth_s3_uri,
        "local_predictions": local_predictions,
        "local_ground_truth": local_ground_truth,
        "note": (
            "This lab sends InvokeEndpoint requests with InferenceId and writes delayed labels in the "
            "SageMaker ground truth JSONL format consumed by native Model Quality Monitor. "
            "Use --label-mode opposite-prediction only to simulate a model-quality alarm."
        ),
    }
    write_metadata(config, "model_quality_capture", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traffic-type", choices=["normal", "drift"], default="normal")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--label-mode", choices=["source", "invert-source", "opposite-prediction"], default="source")
    args = parser.parse_args()
    print(
        json.dumps(
            capture_model_quality_data(
                traffic_type=args.traffic_type,
                limit=args.limit,
                sleep_seconds=args.sleep_seconds,
                label_mode=args.label_mode,
            ),
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
