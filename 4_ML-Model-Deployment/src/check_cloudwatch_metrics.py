from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import Any

from .aws_clients import client_error_code, clients
from .config import load_config, read_json, utc_now, write_json


def _metric(cloudwatch: Any, endpoint_name: str, metric_name: str, stat: str) -> dict[str, Any]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=1)
    response = cloudwatch.get_metric_statistics(
        Namespace="AWS/SageMaker",
        MetricName=metric_name,
        Dimensions=[
            {"Name": "EndpointName", "Value": endpoint_name},
            {"Name": "VariantName", "Value": "AllTraffic"},
        ],
        StartTime=start,
        EndTime=end,
        Period=300,
        Statistics=[stat],
    )
    points = sorted(response.get("Datapoints", []), key=lambda item: item["Timestamp"])
    return {
        "metric": metric_name,
        "stat": stat,
        "datapoints": [
            {"timestamp": item["Timestamp"].isoformat(), "value": item.get(stat)}
            for item in points
        ],
    }


def check_cloudwatch_metrics() -> dict[str, object]:
    config = load_config(require_aws=True)
    cloudwatch = clients(config).cloudwatch
    metric_specs = [
        ("Invocations", "Sum"),
        ("ModelLatency", "Average"),
        ("OverheadLatency", "Average"),
        ("Invocation4XXErrors", "Sum"),
        ("Invocation5XXErrors", "Sum"),
    ]
    metrics = [_metric(cloudwatch, config.endpoint_name, name, stat) for name, stat in metric_specs]
    batch = read_json(config.metadata_path("batch_transform_job.json"), default={})
    metadata = {
        "endpoint_name": config.endpoint_name,
        "metrics": metrics,
        "batch_metrics_note": (
            "Para Batch Transform revisar describe-transform-job, logs del job y metricas "
            "operativas en CloudWatch relacionadas al contenedor."
        ),
        "latest_batch_transform_job": batch.get("transform_job_name", ""),
        "checked_at": utc_now(),
    }
    write_json(config.metadata_path("cloudwatch_metrics.json"), metadata)

    report_path = config.metadata_path("cloudwatch_metrics_report.md")
    lines = ["# CloudWatch metrics report", "", f"- Endpoint: `{config.endpoint_name}`"]
    for metric in metrics:
        lines.append(f"- {metric['metric']} ({metric['stat']}): {len(metric['datapoints'])} datapoints")
    lines.append("")
    lines.append(metadata["batch_metrics_note"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Reporte CloudWatch: {report_path}")
    return metadata


def main() -> None:
    argparse.ArgumentParser(description="Consultar metricas CloudWatch del endpoint.").parse_args()
    try:
        check_cloudwatch_metrics()
    except Exception as exc:
        if client_error_code(exc) in {"AccessDenied", "AccessDeniedException"}:
            raise SystemExit("Permisos insuficientes para consultar CloudWatch.") from exc
        raise


if __name__ == "__main__":
    main()
