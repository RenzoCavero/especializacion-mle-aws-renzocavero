"""Create a CloudWatch alarm for custom Batch Data Quality violations."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata


def create_batch_alarm() -> dict[str, object]:
    config = load_config(validate=True)
    if not config.enable_cloudwatch_alarm:
        payload = {"skipped": True, "reason": "ENABLE_CLOUDWATCH_ALARM=false"}
        write_metadata(config, "batch_cloudwatch_alarm", payload)
        return payload

    native_metadata = read_metadata(config, "batch_monitoring_schedule")
    custom_metadata = read_metadata(config, "custom_batch_data_quality_schedule")
    native_status = str(native_metadata.get("status") or "")
    custom_status = str(custom_metadata.get("status") or "")
    active_alarm_route = "custom_batch_data_quality_fallback"
    if native_status != "native_batch_schedule_unavailable" and custom_status != "created":
        active_alarm_route = "custom_batch_manual_test_metric"

    clients = create_clients(config)
    dimensions = [{"Name": "BatchMonitoringSchedule", "Value": config.batch_monitoring_schedule_name}]
    clients.cloudwatch.put_metric_alarm(
        AlarmName=config.custom_batch_data_quality_alarm_name,
        AlarmDescription="Lab alarm triggered when custom Batch Data Quality violations are detected.",
        ActionsEnabled=True,
        MetricName=config.batch_violations_metric_name,
        Namespace=config.metric_namespace,
        Statistic="Sum",
        Dimensions=dimensions,
        Period=config.alarm_period_seconds,
        EvaluationPeriods=config.alarm_evaluation_periods,
        DatapointsToAlarm=config.alarm_datapoints_to_alarm,
        Threshold=config.alarm_threshold,
        ComparisonOperator="GreaterThanOrEqualToThreshold",
        TreatMissingData=config.alarm_treat_missing_data,
        Tags=config.tags,
    )
    payload = {
        "alarm_name": config.custom_batch_data_quality_alarm_name,
        "native_batch_monitoring_status": native_status or "unknown",
        "custom_batch_schedule_status": custom_status or "unknown",
        "active_alarm_route": active_alarm_route,
        "namespace": config.metric_namespace,
        "metric_name": config.batch_violations_metric_name,
        "dimensions": dimensions,
        "statistic": "Sum",
        "period_seconds": config.alarm_period_seconds,
        "evaluation_periods": config.alarm_evaluation_periods,
        "datapoints_to_alarm": config.alarm_datapoints_to_alarm,
        "threshold": config.alarm_threshold,
        "comparison_operator": "GreaterThanOrEqualToThreshold",
        "treat_missing_data": config.alarm_treat_missing_data,
        "source_scripts": {
            "metric_publisher": "processing/custom_data_quality.py",
            "metric_trigger": "src/start_custom_batch_data_quality_job.py",
            "alarm_creator": "src/create_batch_cloudwatch_alarm.py",
            "eventbridge_rule": "src/create_eventbridge_rule.py",
        },
        "note": (
            "This alarm is driven by the custom Batch Data Quality metric. It is used as the fallback alarm "
            "when native batch Model Monitor schedule creation fails, and it can also be used for manual "
            "batch alarm simulation."
        ),
    }
    write_metadata(config, "batch_cloudwatch_alarm", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(create_batch_alarm(), indent=2, default=str))


if __name__ == "__main__":
    main()
