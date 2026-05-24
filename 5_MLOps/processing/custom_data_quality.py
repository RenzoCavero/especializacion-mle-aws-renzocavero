"""Custom Data Quality evaluator for SageMaker Processing.

This standalone script runs inside a Processing container. It compares a
baseline CSV against recent endpoint input records or an explicit JSONL file,
writes Model Monitor-like violation artifacts, and publishes the lab's custom
CloudWatch violations metric.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import boto3
import pandas as pd


FEATURE_COLUMNS = [
    "age",
    "monthly_spend",
    "support_tickets",
    "tenure_months",
    "late_payments",
    "plan_type",
    "region",
]
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


def _list_objects(s3, uri: str, *, suffixes: tuple[str, ...], window_hours: int | None = None) -> list[dict[str, Any]]:
    bucket, key = _parse_s3_uri(uri)
    if key.endswith(suffixes):
        try:
            response = s3.head_object(Bucket=bucket, Key=key)
            return [{"bucket": bucket, "key": key, "last_modified": response.get("LastModified")}]
        except Exception:
            pass

    cutoff = None
    if window_hours is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    paginator = s3.get_paginator("list_objects_v2")
    objects: list[dict[str, Any]] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=key):
        for item in page.get("Contents", []):
            object_key = str(item.get("Key") or "")
            if not object_key.endswith(suffixes):
                continue
            last_modified = item.get("LastModified")
            if cutoff is not None and last_modified is not None and last_modified < cutoff:
                continue
            objects.append({"bucket": bucket, "key": object_key, "last_modified": last_modified})
    if objects:
        return sorted(objects, key=lambda item: str(item.get("last_modified") or ""))

    if cutoff is None:
        return []

    latest: dict[str, Any] | None = None
    for page in paginator.paginate(Bucket=bucket, Prefix=key):
        for item in page.get("Contents", []):
            object_key = str(item.get("Key") or "")
            if not object_key.endswith(suffixes):
                continue
            if latest is None or item.get("LastModified") > latest.get("last_modified"):
                latest = {"bucket": bucket, "key": object_key, "last_modified": item.get("LastModified")}
    return [latest] if latest else []


def _read_object_text(s3, obj: dict[str, Any]) -> str:
    response = s3.get_object(Bucket=obj["bucket"], Key=obj["key"])
    return response["Body"].read().decode("utf-8")


def _read_baseline_csv(s3, uri: str) -> tuple[pd.DataFrame, list[str]]:
    objects = _list_objects(s3, uri, suffixes=(".csv",))
    if not objects:
        raise ValueError(f"No baseline CSV was found at {uri}")
    text = _read_object_text(s3, objects[-1])
    return pd.read_csv(io.StringIO(text)), [f"s3://{item['bucket']}/{item['key']}" for item in objects[-1:]]


def _decode_capture_data(value: Any, encoding: str = "") -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    text = str(value)
    if encoding.upper() == "BASE64":
        return base64.b64decode(text).decode("utf-8")
    return text


def _record_from_payload(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        if all(column in payload for column in FEATURE_COLUMNS):
            return {column: payload[column] for column in FEATURE_COLUMNS}
        if "instances" in payload and isinstance(payload["instances"], list) and payload["instances"]:
            return _record_from_payload(payload["instances"][0])
        if "features" in payload and isinstance(payload["features"], dict):
            return _record_from_payload(payload["features"])
    if isinstance(payload, list):
        if len(payload) >= len(FEATURE_COLUMNS):
            return {column: payload[index] for index, column in enumerate(FEATURE_COLUMNS)}
    return None


def _parse_json_or_csv_payload(text: str) -> dict[str, Any] | None:
    try:
        return _record_from_payload(json.loads(text))
    except json.JSONDecodeError:
        pass
    rows = list(csv.reader([text]))
    if rows and len(rows[0]) >= len(FEATURE_COLUMNS):
        return {column: rows[0][index] for index, column in enumerate(FEATURE_COLUMNS)}
    return None


def _record_from_jsonl_line(line: str) -> dict[str, Any] | None:
    item = json.loads(line)
    direct = _record_from_payload(item)
    if direct:
        return direct

    capture = item.get("captureData", {}) if isinstance(item, dict) else {}
    endpoint_input = capture.get("endpointInput", {}) if isinstance(capture, dict) else {}
    if not isinstance(endpoint_input, dict):
        return None
    data = _decode_capture_data(endpoint_input.get("data", ""), str(endpoint_input.get("encoding", "")))
    return _parse_json_or_csv_payload(data)


def _read_current_jsonl(s3, uri: str, window_hours: int) -> tuple[pd.DataFrame, list[str]]:
    objects = _list_objects(s3, uri, suffixes=(".jsonl",), window_hours=window_hours)
    if not objects:
        raise ValueError(f"No current JSONL records were found at {uri}")
    records: list[dict[str, Any]] = []
    for obj in objects:
        for line in _read_object_text(s3, obj).splitlines():
            if not line.strip():
                continue
            parsed = _record_from_jsonl_line(line)
            if parsed:
                records.append(parsed)
    if not records:
        raise ValueError(f"No usable feature records were parsed from {uri}")
    return pd.DataFrame(records), [f"s3://{item['bucket']}/{item['key']}" for item in objects]


def _build_violations(baseline: pd.DataFrame, current: pd.DataFrame) -> list[dict[str, object]]:
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
                        "constraint_check_type": "custom_data_quality_mean_shift_check",
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
                        "constraint_check_type": "custom_data_quality_range_check",
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
                        "constraint_check_type": "custom_data_quality_categorical_domain_check",
                        "description": "Current data contains categorical values not observed in baseline.",
                        "unseen_values": unseen_values,
                    }
                )
            baseline_share = baseline_values.value_counts(normalize=True)
            current_share = current_values.value_counts(normalize=True)
            categories = set(baseline_share.index) | set(current_share.index)
            max_delta = max(
                abs(float(current_share.get(item, 0.0)) - float(baseline_share.get(item, 0.0)))
                for item in categories
            )
            if max_delta > 0.25:
                violations.append(
                    {
                        "feature_name": column,
                        "constraint_check_type": "custom_data_quality_categorical_distribution_check",
                        "description": "Current categorical distribution moved by more than 25 percentage points.",
                        "max_share_delta": max_delta,
                    }
                )
    return violations


def _publish_metric(cloudwatch, violations_count: int) -> None:
    dimension_name = _env("METRIC_DIMENSION_NAME", "EndpointName")
    dimension_value = _env("METRIC_DIMENSION_VALUE") or _env("ENDPOINT_NAME", "mlops-lab-endpoint")
    cloudwatch.put_metric_data(
        Namespace=_env("METRIC_NAMESPACE", "MLOps/Lab"),
        MetricData=[
            {
                "MetricName": _env("VIOLATIONS_METRIC_NAME", "DataQualityViolations"),
                "Dimensions": [{"Name": dimension_name, "Value": dimension_value}],
                "Value": float(violations_count),
                "Unit": "Count",
            }
        ],
    )


def main() -> None:
    session = boto3.Session(region_name=_env("AWS_REGION"))
    s3 = session.client("s3")
    cloudwatch = session.client("cloudwatch")
    baseline_uri = _env("BASELINE_DATA_S3_URI")
    current_uri = _env("CURRENT_DATA_S3_URI") or _env("DATA_CAPTURE_S3_URI")
    window_hours = int(_env("CUSTOM_DATA_QUALITY_WINDOW_HOURS", "24"))

    baseline, baseline_objects = _read_baseline_csv(s3, baseline_uri)
    current, current_objects = _read_current_jsonl(s3, current_uri, window_hours)
    violations = _build_violations(baseline, current)
    violations_payload = {
        "version": 0.0,
        "violations": violations,
        "metadata": {
            "source": "custom_data_quality_processing_job",
            "endpoint_name": _env("ENDPOINT_NAME"),
            "baseline_objects": baseline_objects,
            "current_objects": current_objects,
        },
    }
    violations_count = len(violations)
    if violations_count >= 10:
        severity = "critical"
    elif violations_count >= 5:
        severity = "high"
    elif violations_count >= 2:
        severity = "medium"
    elif violations_count == 1:
        severity = "low"
    else:
        severity = "none"
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "custom_data_quality_processing_job",
        "endpoint_name": _env("ENDPOINT_NAME"),
        "baseline_records": int(len(baseline)),
        "current_records": int(len(current)),
        "baseline_objects": baseline_objects,
        "current_objects": current_objects,
        "violations_count": violations_count,
        "severity": severity,
        "violations": violations,
        "published_metric": {
            "namespace": _env("METRIC_NAMESPACE", "MLOps/Lab"),
            "metric_name": _env("VIOLATIONS_METRIC_NAME", "DataQualityViolations"),
            "dimension": {
                _env("METRIC_DIMENSION_NAME", "EndpointName"): (
                    _env("METRIC_DIMENSION_VALUE") or _env("ENDPOINT_NAME")
                )
            },
        },
    }
    _publish_metric(cloudwatch, violations_count)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "constraints_violations.json").write_text(
        json.dumps(violations_payload, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIR / "data_quality_report.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
