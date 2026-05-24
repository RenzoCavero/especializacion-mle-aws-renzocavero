"""Create a CloudWatch alarm for model quality degradation."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata


def create_model_quality_alarm() -> dict[str, object]:
    config = load_config(validate=True)
    if not config.enable_cloudwatch_alarm:
        payload = {"skipped": True, "reason": "ENABLE_CLOUDWATCH_ALARM=false"}
        write_metadata(config, "model_quality_alarm", payload)
        return payload

    clients = create_clients(config)
    schedule_metadata = read_metadata(config, "model_quality_schedule")
    schedule_status = str(schedule_metadata.get("status") or "unknown")
    monitoring_schedule_name = str(
        schedule_metadata.get("actual_model_quality_schedule_name")
        or schedule_metadata.get("model_quality_schedule_name")
        or config.model_quality_schedule_name
    )
    clients.cloudwatch.put_metric_alarm(
        AlarmName=config.model_quality_alarm_name,
        AlarmDescription="Lab alarm triggered when native SageMaker Model Quality f1 drops below the threshold.",
        ActionsEnabled=True,
        MetricName=config.model_quality_native_metric_name,
        Namespace=config.model_quality_metric_namespace,
        Statistic="Average",
        Dimensions=[
            {"Name": "Endpoint", "Value": config.endpoint_name},
            {"Name": "MonitoringSchedule", "Value": monitoring_schedule_name},
        ],
        Period=config.alarm_period_seconds,
        EvaluationPeriods=config.alarm_evaluation_periods,
        DatapointsToAlarm=config.alarm_datapoints_to_alarm,
        Threshold=config.model_quality_f1_threshold,
        ComparisonOperator="LessThanThreshold",
        TreatMissingData=config.alarm_treat_missing_data,
        Tags=config.tags,
    )
    payload = {
        "alarm_name": config.model_quality_alarm_name,
        "namespace": config.model_quality_metric_namespace,
        "metric_name": config.model_quality_native_metric_name,
        "endpoint_name": config.endpoint_name,
        "monitoring_schedule_name": monitoring_schedule_name,
        "dimensions": [
            {"Name": "Endpoint", "Value": config.endpoint_name},
            {"Name": "MonitoringSchedule", "Value": monitoring_schedule_name},
        ],
        "statistic": "Average",
        "period_seconds": config.alarm_period_seconds,
        "evaluation_periods": config.alarm_evaluation_periods,
        "datapoints_to_alarm": config.alarm_datapoints_to_alarm,
        "threshold": config.model_quality_f1_threshold,
        "comparison_operator": "LessThanThreshold",
        "treat_missing_data": config.alarm_treat_missing_data,
        "schedule_status": schedule_status,
        "metric_note": (
            "This alarm receives data only after the native SageMaker Model Quality schedule exists and runs. "
            "If schedule_status is native_model_quality_schedule_unavailable, investigate the SageMaker "
            "CreateMonitoringSchedule/CreateModelQualityJobDefinition control-plane error first."
        ),
        "source_scripts": {
            "metric_source": "SageMaker native Model Quality Monitor",
            "schedule_creator": "src/create_model_quality_schedule.py",
            "alarm_creator": "src/create_model_quality_alarm.py",
            "eventbridge_rule": "src/create_eventbridge_rule.py",
        },
    }
    write_metadata(config, "model_quality_alarm", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(create_model_quality_alarm(), indent=2, default=str))


if __name__ == "__main__":
    main()
