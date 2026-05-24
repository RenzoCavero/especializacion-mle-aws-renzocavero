"""Create a SageMaker Model Quality Monitor baseline job."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, fbeta_score, precision_score, recall_score, roc_auc_score

from .aws_clients import create_clients
from .compute import select_instance_type
from .config import load_config, read_metadata, write_metadata
from .create_monitoring_schedule import model_monitor_image_uri


BASELINE_COLUMNS = ["probability", "prediction", "label"]


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    bucket_key = uri[5:]
    bucket, _, key = bucket_key.partition("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI without bucket/key: {uri}")
    return bucket, key.rstrip("/")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def _job_name(config) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{config.resource_prefix}-model-quality-baseline-{timestamp}"[:63].strip("-")


def _safe_rate(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _metric_constraint(value: float, operator: str, *, floor: float | None = None, ceiling: float | None = None) -> dict[str, object]:
    threshold = float(value)
    if floor is not None:
        threshold = max(threshold, floor)
    if ceiling is not None:
        threshold = min(threshold, ceiling)
    return {"threshold": threshold, "comparison_operator": operator}


def _metric_value(value: float) -> dict[str, object]:
    return {"value": float(value), "standard_deviation": "NaN"}


def _build_model_quality_artifacts(joined: pd.DataFrame, config) -> tuple[dict[str, object], dict[str, object]]:
    y_true = joined["label"].astype(int)
    y_pred = joined["prediction"].astype(int)
    y_prob = joined["probability"].astype(float)
    tn, fp, fn, tp = [int(value) for value in pd.crosstab(y_true, y_pred).reindex(index=[0, 1], columns=[0, 1], fill_value=0).to_numpy().ravel()]

    accuracy = float(accuracy_score(y_true, y_pred))
    precision = float(precision_score(y_true, y_pred, zero_division=0))
    recall = float(recall_score(y_true, y_pred, zero_division=0))
    f0_5 = float(fbeta_score(y_true, y_pred, beta=0.5, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    f2 = float(fbeta_score(y_true, y_pred, beta=2.0, zero_division=0))
    auc = float(roc_auc_score(y_true, y_prob)) if y_true.nunique() > 1 else 0.0
    true_positive_rate = _safe_rate(tp, tp + fn)
    true_negative_rate = _safe_rate(tn, tn + fp)
    false_positive_rate = _safe_rate(fp, fp + tn)
    false_negative_rate = _safe_rate(fn, fn + tp)

    metrics = {
        "confusion_matrix": {
            "0": {"0": tn, "1": fp},
            "1": {"0": fn, "1": tp},
        },
        "recall": _metric_value(recall),
        "precision": _metric_value(precision),
        "accuracy": _metric_value(accuracy),
        "true_positive_rate": _metric_value(true_positive_rate),
        "true_negative_rate": _metric_value(true_negative_rate),
        "false_positive_rate": _metric_value(false_positive_rate),
        "false_negative_rate": _metric_value(false_negative_rate),
        "auc": _metric_value(auc),
        "f0_5": _metric_value(f0_5),
        "f1": _metric_value(f1),
        "f2": _metric_value(f2),
    }
    statistics = {
        "version": 0.0,
        "binary_classification_metrics": metrics,
    }
    constraints = {
        "version": 0.0,
        "binary_classification_constraints": {
            "recall": _metric_constraint(recall * 0.9, "LessThanThreshold"),
            "precision": _metric_constraint(precision * 0.9, "LessThanThreshold"),
            "accuracy": _metric_constraint(accuracy * 0.9, "LessThanThreshold", floor=config.model_quality_accuracy_threshold),
            "true_positive_rate": _metric_constraint(true_positive_rate * 0.9, "LessThanThreshold"),
            "true_negative_rate": _metric_constraint(true_negative_rate * 0.9, "LessThanThreshold"),
            "false_positive_rate": _metric_constraint(false_positive_rate + 0.1, "GreaterThanThreshold", ceiling=1.0),
            "false_negative_rate": _metric_constraint(false_negative_rate + 0.1, "GreaterThanThreshold", ceiling=1.0),
            "auc": _metric_constraint(auc * 0.9, "LessThanThreshold", floor=config.model_quality_auc_threshold),
            "f0_5": _metric_constraint(f0_5 * 0.9, "LessThanThreshold"),
            "f1": _metric_constraint(f1 * 0.9, "LessThanThreshold", floor=config.model_quality_f1_threshold),
            "f2": _metric_constraint(f2 * 0.9, "LessThanThreshold"),
        },
    }
    return statistics, constraints


def _put_json(clients, uri: str, payload: dict[str, object]) -> None:
    bucket, key = _parse_s3_uri(uri)
    clients.s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=(json.dumps(payload, indent=2, default=str) + "\n").encode("utf-8"),
        ContentType="application/json",
    )


def _prepare_baseline_dataset(clients, config) -> tuple[str, int, pd.DataFrame]:
    metadata = read_metadata(config, "model_quality_capture")
    if not metadata:
        raise FileNotFoundError("No model_quality_capture metadata found. Run src.capture_model_quality_data first.")

    predictions_path = Path(str(metadata.get("local_predictions") or ""))
    ground_truth_path = Path(str(metadata.get("local_ground_truth") or ""))
    if not predictions_path.exists() or not ground_truth_path.exists():
        raise FileNotFoundError(
            "Local model quality prediction/ground-truth files are missing. "
            "Run src.capture_model_quality_data again."
        )

    predictions = pd.DataFrame(_read_jsonl(predictions_path))
    ground_truth = pd.DataFrame(_read_jsonl(ground_truth_path))
    joined = predictions.merge(
        ground_truth[["inference_id", "label"]],
        on="inference_id",
        how="inner",
        validate="one_to_one",
    )
    if joined.empty:
        raise ValueError("No joined prediction/ground-truth rows found for model quality baseline.")

    baseline = joined[BASELINE_COLUMNS].copy()
    baseline["prediction"] = baseline["prediction"].astype(int)
    baseline["label"] = baseline["label"].astype(int)
    baseline["probability"] = baseline["probability"].astype(float)

    bucket, key = _parse_s3_uri(config.model_quality_baseline_dataset_s3_uri)
    clients.s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=baseline.to_csv(index=False).encode("utf-8"),
        ContentType="text/csv",
    )
    return config.model_quality_baseline_dataset_s3_uri, int(len(baseline)), joined


def _validate_or_synthesize_artifacts(clients, config, joined: pd.DataFrame) -> dict[str, object]:
    constraints_bucket, constraints_key = _parse_s3_uri(config.model_quality_constraints_s3_uri)
    constraints = json.loads(
        clients.s3.get_object(Bucket=constraints_bucket, Key=constraints_key)["Body"].read().decode("utf-8")
    )
    statistics_bucket, statistics_key = _parse_s3_uri(config.model_quality_statistics_s3_uri)
    try:
        statistics = json.loads(
            clients.s3.get_object(Bucket=statistics_bucket, Key=statistics_key)["Body"].read().decode("utf-8")
        )
    except Exception:
        statistics = {}
    original_constraint_sections = sorted(str(key) for key in constraints.keys())
    original_statistics_sections = sorted(str(key) for key in statistics.keys())
    has_binary_constraints = isinstance(constraints.get("binary_classification_constraints"), dict)
    has_binary_statistics = isinstance(statistics.get("binary_classification_metrics"), dict)
    synthesized = False
    if not has_binary_constraints or not has_binary_statistics:
        statistics, constraints = _build_model_quality_artifacts(joined, config)
        _put_json(clients, config.model_quality_statistics_s3_uri, statistics)
        _put_json(clients, config.model_quality_constraints_s3_uri, constraints)
        synthesized = True
    return {
        "has_binary_classification_constraints": isinstance(
            constraints.get("binary_classification_constraints"),
            dict,
        ),
        "has_binary_classification_metrics": isinstance(
            statistics.get("binary_classification_metrics"),
            dict,
        ),
        "synthesized_model_quality_artifacts": synthesized,
        "constraint_sections": sorted(str(key) for key in constraints.keys()),
        "statistics_sections": sorted(str(key) for key in statistics.keys()),
        "original_constraint_sections": original_constraint_sections,
        "original_statistics_sections": original_statistics_sections,
    }


def _model_quality_baseline_environment(config) -> dict[str, str]:
    return {
        "analysis_type": "MODEL_QUALITY",
        "dataset_format": json.dumps({"csv": {"header": True}}),
        "dataset_source": "/opt/ml/processing/sm_input",
        "output_path": "/opt/ml/processing/sm_output",
        "problem_type": config.model_quality_problem_type,
        "inference_attribute": config.model_quality_inference_attribute,
        "probability_attribute": config.model_quality_probability_attribute,
        "ground_truth_attribute": "label",
        "publish_cloudwatch_metrics": "Disabled",
    }


def generate_model_quality_baseline(
    wait: bool = False,
    poll_seconds: int = 30,
    timeout_seconds: int = 2400,
) -> dict[str, object]:
    config = load_config(validate=True, require_execution_role=True)
    if poll_seconds <= 0:
        raise ValueError("--poll-seconds must be greater than 0")
    if not config.enable_model_monitor:
        payload = {"skipped": True, "reason": "ENABLE_MODEL_MONITOR=false"}
        write_metadata(config, "model_quality_baseline", payload)
        return payload

    clients = create_clients(config)
    processing_compute = select_instance_type(
        config,
        workload="processing",
        preferred=config.model_monitor_processing_instance_type,
        candidates=config.model_monitor_processing_instance_type_candidates_list,
        session=clients.session,
    )
    if processing_compute.source == "fallback-no-positive-quota":
        raise RuntimeError("No SageMaker processing quota is available for Model Quality baseline jobs.")

    baseline_dataset_s3_uri, rows, joined = _prepare_baseline_dataset(clients, config)
    job_name = _job_name(config)
    image_uri = model_monitor_image_uri(config)
    clients.sagemaker.create_processing_job(
        ProcessingJobName=job_name,
        RoleArn=config.sagemaker_execution_role_arn,
        AppSpecification={"ImageUri": image_uri},
        Environment=_model_quality_baseline_environment(config),
        ProcessingResources={
            "ClusterConfig": {
                "InstanceCount": 1,
                "InstanceType": processing_compute.selected_instance_type,
                "VolumeSizeInGB": 20,
            }
        },
        ProcessingInputs=[
            {
                "InputName": "model-quality-baseline-data",
                "S3Input": {
                    "S3Uri": baseline_dataset_s3_uri,
                    "LocalPath": "/opt/ml/processing/sm_input",
                    "S3DataType": "S3Prefix",
                    "S3InputMode": "File",
                    "S3DataDistributionType": "FullyReplicated",
                    "S3CompressionType": "None",
                },
            }
        ],
        ProcessingOutputConfig={
            "Outputs": [
                {
                    "OutputName": "model-quality-baseline",
                    "S3Output": {
                        "S3Uri": config.model_quality_baseline_s3_uri,
                        "LocalPath": "/opt/ml/processing/sm_output",
                        "S3UploadMode": "EndOfJob",
                    },
                }
            ]
        },
        StoppingCondition={"MaxRuntimeInSeconds": 1800},
        Tags=config.tags,
    )

    description: dict[str, object] = {}
    artifact_validation: dict[str, object] = {}
    if wait:
        started_at = time.monotonic()
        print(
            "Model quality baseline processing job started: "
            f"{job_name} on {processing_compute.selected_instance_type}. "
            f"Local wait timeout: {timeout_seconds}s."
        )
        while True:
            description = clients.sagemaker.describe_processing_job(ProcessingJobName=job_name)
            status = str(description.get("ProcessingJobStatus"))
            if status in {"Completed", "Failed", "Stopped"}:
                break
            elapsed_seconds = int(time.monotonic() - started_at)
            if timeout_seconds > 0 and elapsed_seconds >= timeout_seconds:
                raise TimeoutError(
                    f"Model quality baseline job {job_name} is still {status} after {elapsed_seconds}s."
                )
            print(f"Model quality baseline job status: {status}. Waiting {poll_seconds}s...")
            time.sleep(poll_seconds)
        if description.get("ProcessingJobStatus") != "Completed":
            raise RuntimeError(
                f"Model quality baseline job {job_name} ended with status "
                f"{description.get('ProcessingJobStatus')}: {description.get('FailureReason', '')}"
            )
        artifact_validation = _validate_or_synthesize_artifacts(clients, config, joined)

    payload = {
        "baseline_job_name": job_name,
        "baseline_job_type": "SageMaker Model Quality baseline Processing Job",
        "baseline_dataset": baseline_dataset_s3_uri,
        "baseline_rows": rows,
        "baseline_columns": BASELINE_COLUMNS,
        "model_quality_baseline_s3_uri": config.model_quality_baseline_s3_uri,
        "model_quality_constraints_s3_uri": config.model_quality_constraints_s3_uri,
        "model_quality_statistics_s3_uri": config.model_quality_statistics_s3_uri,
        "problem_type": config.model_quality_problem_type,
        "image_uri": image_uri,
        "compute_selection": processing_compute.to_dict(),
        "artifact_validation": artifact_validation,
        "processing_job_description": description,
        "cost_warning": "Model Quality baseline jobs generate SageMaker Processing cost.",
    }
    write_metadata(config, "model_quality_baseline", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=int, default=2400)
    args = parser.parse_args()
    print(
        json.dumps(
            generate_model_quality_baseline(
                wait=args.wait,
                poll_seconds=args.poll_seconds,
                timeout_seconds=args.timeout_seconds,
            ),
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
