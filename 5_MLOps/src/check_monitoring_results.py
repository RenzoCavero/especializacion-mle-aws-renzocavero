"""Find Model Monitor violations and publish a custom metric."""

from __future__ import annotations

import argparse
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .generate_sample_data import FEATURE_COLUMNS
from monitoring.monitoring_report import write_monitoring_report
from monitoring.parse_violations import parse_violations
from monitoring.publish_custom_metric import publish_violations_metric

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata


def _read_json_from_s3(clients, bucket: str, key: str) -> dict:
    obj = clients.s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read().decode("utf-8"))


def _read_baseline_frame(clients, config) -> pd.DataFrame:
    local_path = config.local_cache_dir / "baseline.csv"
    if local_path.exists():
        return pd.read_csv(local_path)
    obj = clients.s3.get_object(
        Bucket=config.s3_bucket_name,
        Key=f"{config.resource_prefix}/{config.environment}/data/raw/baseline_monitor.csv",
    )
    return pd.read_csv(io.BytesIO(obj["Body"].read()))


def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def _fallback_current_frame(config) -> tuple[pd.DataFrame, str]:
    drift_path = config.local_cache_dir / "inference_drift.jsonl"
    normal_path = config.local_cache_dir / "inference_normal.jsonl"
    if drift_path.exists():
        return pd.DataFrame(_read_jsonl(drift_path)), str(drift_path)
    if normal_path.exists():
        return pd.DataFrame(_read_jsonl(normal_path)), str(normal_path)
    raise FileNotFoundError("No local inference JSONL files found. Run step 02 and step 10 traffic simulation.")


def _build_fallback_violations(baseline: pd.DataFrame, current: pd.DataFrame, source_path: str) -> dict[str, object]:
    violations: list[dict[str, object]] = []
    for column in FEATURE_COLUMNS:
        if column not in baseline.columns or column not in current.columns:
            continue
        baseline_numeric = pd.to_numeric(baseline[column], errors="coerce")
        current_numeric = pd.to_numeric(current[column], errors="coerce")
        if baseline_numeric.notna().all() and current_numeric.notna().all():
            base_mean = float(baseline_numeric.mean())
            current_mean = float(current_numeric.mean())
            base_std = float(baseline_numeric.std() or 0.0)
            shift_threshold = max(base_std * 2, 1e-6)
            if abs(current_mean - base_mean) > shift_threshold:
                violations.append(
                    {
                        "feature_name": column,
                        "constraint_check_type": "lab_fallback_mean_shift_check",
                        "description": "Current mean moved more than two baseline standard deviations.",
                        "baseline_mean": base_mean,
                        "current_mean": current_mean,
                        "threshold": shift_threshold,
                    }
                )
            base_min = float(baseline_numeric.min())
            base_max = float(baseline_numeric.max())
            current_min = float(current_numeric.min())
            current_max = float(current_numeric.max())
            if current_min < base_min or current_max > base_max:
                violations.append(
                    {
                        "feature_name": column,
                        "constraint_check_type": "lab_fallback_range_check",
                        "description": "Current values exceed the observed baseline range.",
                        "baseline_min": base_min,
                        "baseline_max": base_max,
                        "current_min": current_min,
                        "current_max": current_max,
                    }
                )
        else:
            baseline_values = baseline[column].astype(str)
            current_values = current[column].astype(str)
            baseline_domain = set(baseline_values.dropna().unique())
            current_domain = set(current_values.dropna().unique())
            unseen_values = sorted(current_domain - baseline_domain)
            if unseen_values:
                violations.append(
                    {
                        "feature_name": column,
                        "constraint_check_type": "lab_fallback_categorical_domain_check",
                        "description": "Current data contains categorical values not observed in baseline.",
                        "unseen_values": unseen_values,
                    }
                )
            baseline_share = baseline_values.value_counts(normalize=True)
            current_share = current_values.value_counts(normalize=True)
            categories = set(baseline_share.index) | set(current_share.index)
            max_delta = max(abs(float(current_share.get(item, 0.0)) - float(baseline_share.get(item, 0.0))) for item in categories)
            if max_delta > 0.25:
                violations.append(
                    {
                        "feature_name": column,
                        "constraint_check_type": "lab_fallback_categorical_distribution_check",
                        "description": "Current categorical distribution moved by more than 25 percentage points.",
                        "max_share_delta": max_delta,
                    }
                )
    return {
        "version": 0.0,
        "violations": violations,
        "metadata": {
            "source": "lab_fallback_local_analyzer",
            "input_path": source_path,
            "note": (
                "Generated because SageMaker CreateMonitoringSchedule returned repeated InternalFailure. "
                "This keeps the lab flow moving, but native SageMaker Model Monitor schedules remain the production target."
            ),
        },
    }


def _write_fallback_violations(clients, config, payload: dict[str, object]) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d/%H%M%S")
    key = f"{config.resource_prefix}/{config.environment}/monitoring/fallback/{timestamp}/constraints_violations.json"
    clients.s3.put_object(
        Bucket=config.s3_bucket_name,
        Key=key,
        Body=(json.dumps(payload, indent=2, default=str) + "\n").encode("utf-8"),
        ContentType="application/json",
    )
    return key


def _fallback_monitoring_if_needed(clients, config) -> tuple[dict[str, object], str] | None:
    schedule_metadata = read_metadata(config, "monitoring_schedule")
    if schedule_metadata.get("status") != "native_schedule_unavailable":
        return None
    baseline = _read_baseline_frame(clients, config)
    current, source_path = _fallback_current_frame(config)
    payload = _build_fallback_violations(baseline, current, source_path)
    key = _write_fallback_violations(clients, config, payload)
    return payload, f"s3://{config.s3_bucket_name}/{key}"


def _list_violation_objects(clients, config) -> list[dict[str, object]]:
    prefix = f"{config.resource_prefix}/{config.environment}/monitoring"
    paginator = clients.s3.get_paginator("list_objects_v2")
    objects: list[dict[str, object]] = []
    for page in paginator.paginate(Bucket=config.s3_bucket_name, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item.get("Key", "")
            if isinstance(key, str) and key.endswith("constraints_violations.json"):
                objects.append({"Key": key, "LastModified": item.get("LastModified")})
    return objects


def check_results(publish_metric: bool = True) -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)

    fallback = _fallback_monitoring_if_needed(clients, config)
    if fallback:
        fallback_payload, latest_uri = fallback
        parsed = parse_violations(fallback_payload)
        parsed["fallback_monitoring"] = True
    else:
        candidates = _list_violation_objects(clients, config)
        if candidates:
            latest = max(
                candidates,
                key=lambda item: item.get("LastModified") or datetime.min.replace(tzinfo=timezone.utc),
            )
            latest_key = str(latest["Key"])
            parsed = parse_violations(_read_json_from_s3(clients, config.s3_bucket_name, latest_key))
            latest_uri = f"s3://{config.s3_bucket_name}/{latest_key}"
        else:
            parsed = {"violations_count": 0, "severity": "none", "by_feature": {}, "violations": []}
            latest_uri = ""

    summary = {
        "endpoint_name": config.endpoint_name,
        "latest_violations_uri": latest_uri,
        **parsed,
    }
    if publish_metric:
        publish_violations_metric(config, int(summary["violations_count"]))
        summary["published_metric"] = {
            "namespace": config.metric_namespace,
            "metric_name": config.violations_metric_name,
        }
    report_path = write_monitoring_report(config.local_outputs_dir / "monitoring_report.md", summary)
    summary["local_report"] = str(report_path)
    write_metadata(config, "monitoring_results", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-publish-metric", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check_results(publish_metric=not args.no_publish_metric), indent=2, default=str))


if __name__ == "__main__":
    main()
