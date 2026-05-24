"""Create a CloudWatch alarm for Data Quality drift violations."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata


def _active_data_quality_alarm_name(config) -> tuple[str, str]:
    schedule = read_metadata(config, "monitoring_schedule")
    custom_schedule = read_metadata(config, "custom_data_quality_schedule")
    if schedule.get("status") == "native_schedule_unavailable" or custom_schedule.get("status") == "created":
        return config.custom_data_quality_alarm_name, "custom_data_quality_fallback"
    return config.alarm_name, "native_data_quality"


def create_alarm() -> dict[str, object]:
    config = load_config(validate=True)
    if not config.enable_cloudwatch_alarm:
        payload = {"skipped": True, "reason": "ENABLE_CLOUDWATCH_ALARM=false"}
        write_metadata(config, "cloudwatch_alarm", payload)
        return payload

    clients = create_clients(config)
    alarm_name, alarm_route = _active_data_quality_alarm_name(config)
    clients.cloudwatch.put_metric_alarm(
        AlarmName=alarm_name,
        AlarmDescription="Lab alarm triggered when Data Quality violations are detected.",
        ActionsEnabled=True,
        MetricName=config.violations_metric_name,
        Namespace=config.metric_namespace,
        Statistic="Sum",
        Dimensions=[{"Name": "EndpointName", "Value": config.endpoint_name}],
        Period=config.alarm_period_seconds,
        EvaluationPeriods=config.alarm_evaluation_periods,
        DatapointsToAlarm=config.alarm_datapoints_to_alarm,
        Threshold=config.alarm_threshold,
        ComparisonOperator="GreaterThanOrEqualToThreshold",
        TreatMissingData=config.alarm_treat_missing_data,
        Tags=config.tags,
    )
    payload = {
        "alarm_name": alarm_name,
        "configured_data_quality_alarm_name": config.alarm_name,
        "configured_custom_data_quality_alarm_name": config.custom_data_quality_alarm_name,
        "active_alarm_route": alarm_route,
        "namespace": config.metric_namespace,
        "metric_name": config.violations_metric_name,
        "endpoint_name": config.endpoint_name,
        "dimensions": [{"Name": "EndpointName", "Value": config.endpoint_name}],
        "statistic": "Sum",
        "period_seconds": config.alarm_period_seconds,
        "evaluation_periods": config.alarm_evaluation_periods,
        "datapoints_to_alarm": config.alarm_datapoints_to_alarm,
        "threshold": config.alarm_threshold,
        "comparison_operator": "GreaterThanOrEqualToThreshold",
        "treat_missing_data": config.alarm_treat_missing_data,
        "source_scripts": {
            "metric_publisher": "monitoring/publish_custom_metric.py",
            "metric_trigger": "src/check_monitoring_results.py",
            "alarm_creator": "src/create_cloudwatch_alarm.py",
            "eventbridge_rule": "src/create_eventbridge_rule.py",
        },
    }
    write_metadata(config, "cloudwatch_alarm", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(create_alarm(), indent=2))


if __name__ == "__main__":
    main()
