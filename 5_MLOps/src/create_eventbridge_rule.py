"""Create an EventBridge rule routing CloudWatch alarm events to Step Functions and SNS."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata


def create_rule() -> dict[str, object]:
    config = load_config(validate=True)
    if not config.enable_eventbridge:
        payload = {"skipped": True, "reason": "ENABLE_EVENTBRIDGE=false"}
        write_metadata(config, "eventbridge_rule", payload)
        return payload

    clients = create_clients(config)
    alarm_names = list(
        dict.fromkeys(
            [
                config.alarm_name,
                config.custom_data_quality_alarm_name,
                config.custom_batch_data_quality_alarm_name,
                config.model_quality_alarm_name,
                config.custom_model_quality_alarm_name,
            ]
        )
    )
    event_pattern = {
        "source": ["aws.cloudwatch"],
        "detail-type": ["CloudWatch Alarm State Change"],
        "detail": {"alarmName": alarm_names, "state": {"value": ["ALARM"]}},
    }
    response = clients.events.put_rule(
        Name=config.eventbridge_rule_name,
        EventPattern=json.dumps(event_pattern),
        State="ENABLED",
        Description="Route MLOps data/model quality alarms to Step Functions and SNS.",
        Tags=[{"Key": item["Key"], "Value": item["Value"]} for item in config.tags],
    )

    feedback = read_metadata(config, "feedback_loop")
    notifications = read_metadata(config, "alarm_notifications")
    state_machine_arn = feedback.get("state_machine_arn")
    targets = []
    target_status = {"stepfunctions": "not_configured", "sns": "not_configured"}
    if state_machine_arn and config.eventbridge_to_sfn_role_arn:
        targets.append(
            {
                "Id": "MLOpsFeedbackLoop",
                "Arn": str(state_machine_arn),
                "RoleArn": config.eventbridge_to_sfn_role_arn,
            }
        )
        target_status["stepfunctions"] = "configured"
    topic_arn = str(notifications.get("topic_arn") or "")
    if topic_arn:
        targets.append({"Id": "AlarmEmailSns", "Arn": topic_arn})
        target_status["sns"] = "configured"
    if targets:
        clients.events.put_targets(Rule=config.eventbridge_rule_name, Targets=targets)

    payload = {
        "rule_name": config.eventbridge_rule_name,
        "rule_arn": response.get("RuleArn"),
        "event_pattern": event_pattern,
        "alarm_names": alarm_names,
        "target_status": target_status,
        "state_machine_arn": state_machine_arn or "",
        "sns_topic_arn": topic_arn,
        "note": (
            "This single EventBridge rule has two optional targets: Step Functions for automated diagnosis "
            "and SNS for email notification. Set EVENTBRIDGE_TO_SFN_ROLE_ARN to connect the Step Functions target. "
            "Run src.create_alarm_notifications before this command to route ALARM events to SNS email."
        ),
    }
    write_metadata(config, "eventbridge_rule", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(create_rule(), indent=2, default=str))


if __name__ == "__main__":
    main()
