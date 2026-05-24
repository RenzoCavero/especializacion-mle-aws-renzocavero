"""Create a CloudWatch alarm for the custom Model Quality fallback metric."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, write_metadata


def create_custom_model_quality_alarm() -> dict[str, object]:
    config = load_config(validate=True)
    if not config.enable_cloudwatch_alarm:
        payload = {"skipped": True, "reason": "ENABLE_CLOUDWATCH_ALARM=false"}
        write_metadata(config, "custom_model_quality_alarm", payload)
        return payload

    clients = create_clients(config)
    clients.cloudwatch.put_metric_alarm(
        AlarmName=config.custom_model_quality_alarm_name,
        AlarmDescription="Lab alarm triggered when custom Model Quality F1 drops below the threshold.",
        ActionsEnabled=True,
        MetricName=config.model_quality_f1_metric_name,
        Namespace=config.metric_namespace,
        Statistic="Average",
        Dimensions=[{"Name": "EndpointName", "Value": config.endpoint_name}],
        Period=config.alarm_period_seconds,
        EvaluationPeriods=config.alarm_evaluation_periods,
        DatapointsToAlarm=config.alarm_datapoints_to_alarm,
        Threshold=config.model_quality_f1_threshold,
        ComparisonOperator="LessThanThreshold",
        TreatMissingData=config.alarm_treat_missing_data,
        Tags=config.tags,
    )
    payload = {
        "alarm_name": config.custom_model_quality_alarm_name,
        "namespace": config.metric_namespace,
        "metric_name": config.model_quality_f1_metric_name,
        "endpoint_name": config.endpoint_name,
        "dimensions": [{"Name": "EndpointName", "Value": config.endpoint_name}],
        "statistic": "Average",
        "period_seconds": config.alarm_period_seconds,
        "evaluation_periods": config.alarm_evaluation_periods,
        "datapoints_to_alarm": config.alarm_datapoints_to_alarm,
        "threshold": config.model_quality_f1_threshold,
        "comparison_operator": "LessThanThreshold",
        "treat_missing_data": config.alarm_treat_missing_data,
        "note": (
            "This alarm is driven by the custom Model Quality Processing Job fallback, "
            "which publishes MLOps/Lab custom metrics."
        ),
    }
    write_metadata(config, "custom_model_quality_alarm", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(create_custom_model_quality_alarm(), indent=2, default=str))


if __name__ == "__main__":
    main()
