"""Evaluate model performance by joining predictions with delayed ground truth."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

from monitoring.publish_custom_metric import publish_model_quality_metrics

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    bucket_key = uri[5:]
    bucket, _, key = bucket_key.partition("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI without bucket/key: {uri}")
    return bucket, key


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def _put_json(clients, uri: str, payload: dict[str, Any]) -> str:
    bucket, key = _parse_s3_uri(uri)
    clients.s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=(json.dumps(payload, indent=2, default=str) + "\n").encode("utf-8"),
        ContentType="application/json",
    )
    return uri


def _load_capture_frames(config) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    metadata = read_metadata(config, "model_quality_capture")
    if not metadata:
        raise FileNotFoundError("No model_quality_capture metadata found. Run step 09 capture first.")
    predictions_path = Path(str(metadata.get("local_predictions") or ""))
    ground_truth_path = Path(str(metadata.get("local_ground_truth") or ""))
    if not predictions_path.exists() or not ground_truth_path.exists():
        raise FileNotFoundError(
            "Local model quality prediction/ground truth files are missing. "
            "Rerun `python -m src.capture_model_quality_data`."
        )
    predictions = pd.DataFrame(_read_jsonl(predictions_path))
    ground_truth = pd.DataFrame(_read_jsonl(ground_truth_path))
    return predictions, ground_truth, metadata


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


def _quality_status(config, metrics: dict[str, float | int | None]) -> dict[str, object]:
    records = int(metrics.get("records_evaluated") or 0)
    checks: dict[str, object] = {
        "min_records": {
            "value": records,
            "threshold": config.model_quality_min_records,
            "passed": records >= config.model_quality_min_records,
        },
        "accuracy": {
            "value": metrics.get("accuracy"),
            "threshold": config.model_quality_accuracy_threshold,
            "passed": float(metrics.get("accuracy") or 0.0) >= config.model_quality_accuracy_threshold,
        },
        "f1": {
            "value": metrics.get("f1"),
            "threshold": config.model_quality_f1_threshold,
            "passed": float(metrics.get("f1") or 0.0) >= config.model_quality_f1_threshold,
        },
    }
    auc = metrics.get("auc")
    checks["auc"] = {
        "value": auc,
        "threshold": config.model_quality_auc_threshold,
        "passed": None if auc is None else float(auc) >= config.model_quality_auc_threshold,
    }
    required_results = [
        bool(checks["min_records"]["passed"]),
        bool(checks["accuracy"]["passed"]),
        bool(checks["f1"]["passed"]),
    ]
    if auc is not None:
        required_results.append(bool(checks["auc"]["passed"]))
    status = "pass" if all(required_results) else "fail"
    if records < config.model_quality_min_records:
        status = "insufficient_data"
    return {"status": status, "checks": checks}


def _write_report(path: Path, summary: dict[str, object]) -> str:
    lines = [
        "# Model Quality Report",
        "",
        f"- Endpoint: `{summary.get('endpoint_name', '')}`",
        f"- Traffic type: `{summary.get('traffic_type', '')}`",
        f"- Status: `{summary.get('status', '')}`",
        f"- Records evaluated: `{summary.get('metrics', {}).get('records_evaluated', 0)}`",
        f"- Accuracy: `{summary.get('metrics', {}).get('accuracy')}`",
        f"- F1: `{summary.get('metrics', {}).get('f1')}`",
        f"- AUC: `{summary.get('metrics', {}).get('auc')}`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def check_model_quality(publish_metric: bool = True) -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    predictions, ground_truth, capture_metadata = _load_capture_frames(config)
    joined = predictions.merge(
        ground_truth[["inference_id", "label"]],
        on="inference_id",
        how="inner",
        validate="one_to_one",
    )
    if joined.empty:
        raise ValueError("No joined prediction/ground truth rows found by inference_id.")

    metrics = _compute_metrics(joined)
    status = _quality_status(config, metrics)
    timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d/%H%M%S")
    summary: dict[str, object] = {
        "endpoint_name": config.endpoint_name,
        "traffic_type": capture_metadata.get("traffic_type", ""),
        "prediction_records": int(len(predictions)),
        "ground_truth_records": int(len(ground_truth)),
        "joined_records": int(len(joined)),
        "metrics": metrics,
        **status,
        "thresholds": {
            "accuracy": config.model_quality_accuracy_threshold,
            "f1": config.model_quality_f1_threshold,
            "auc": config.model_quality_auc_threshold,
            "min_records": config.model_quality_min_records,
        },
        "source_predictions_s3_uri": capture_metadata.get("predictions_s3_uri", ""),
        "source_ground_truth_s3_uri": capture_metadata.get("ground_truth_s3_uri", ""),
    }
    if publish_metric:
        publish_model_quality_metrics(config, metrics)
        summary["published_metrics"] = {
            "namespace": config.metric_namespace,
            "metric_names": [
                config.model_quality_records_metric_name,
                config.model_quality_accuracy_metric_name,
                config.model_quality_f1_metric_name,
                config.model_quality_auc_metric_name,
            ],
        }

    report_s3_uri = f"{config.model_quality_reports_s3_uri}/{timestamp}/model_quality_report.json"
    _put_json(clients, report_s3_uri, summary)
    summary["report_s3_uri"] = report_s3_uri
    summary["local_report"] = _write_report(config.local_outputs_dir / "model_quality_report.md", summary)
    write_metadata(config, "model_quality_results", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-publish-metric", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check_model_quality(publish_metric=not args.no_publish_metric), indent=2, default=str))


if __name__ == "__main__":
    main()
