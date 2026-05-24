"""Publish Data Quality and Model Quality custom CloudWatch metrics."""

from __future__ import annotations

from src.aws_clients import create_clients
from src.config import LabConfig


def publish_violations_metric(config: LabConfig, violations_count: int) -> None:
    clients = create_clients(config)
    clients.cloudwatch.put_metric_data(
        Namespace=config.metric_namespace,
        MetricData=[
            {
                "MetricName": config.violations_metric_name,
                "Dimensions": [{"Name": "EndpointName", "Value": config.endpoint_name}],
                "Value": float(violations_count),
                "Unit": "Count",
            }
        ],
    )


def publish_model_quality_metrics(config: LabConfig, metrics: dict[str, float | int | None]) -> None:
    clients = create_clients(config)
    metric_data = [
        {
            "MetricName": config.model_quality_records_metric_name,
            "Dimensions": [{"Name": "EndpointName", "Value": config.endpoint_name}],
            "Value": float(metrics.get("records_evaluated") or 0),
            "Unit": "Count",
        }
    ]
    optional_metrics = [
        ("accuracy", config.model_quality_accuracy_metric_name),
        ("f1", config.model_quality_f1_metric_name),
        ("auc", config.model_quality_auc_metric_name),
    ]
    for key, metric_name in optional_metrics:
        value = metrics.get(key)
        if value is None:
            continue
        metric_data.append(
            {
                "MetricName": metric_name,
                "Dimensions": [{"Name": "EndpointName", "Value": config.endpoint_name}],
                "Value": float(value),
                "Unit": "None",
            }
        )
    clients.cloudwatch.put_metric_data(Namespace=config.metric_namespace, MetricData=metric_data)
