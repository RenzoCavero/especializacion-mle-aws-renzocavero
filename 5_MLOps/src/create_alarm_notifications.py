"""Create SNS email notifications for alarm events routed by EventBridge."""

from __future__ import annotations

import argparse
import json

from .aws_clients import create_clients
from .config import load_config, write_metadata


def _eventbridge_rule_arn(config, account_id: str) -> str:
    return f"arn:aws:events:{config.aws_region}:{account_id}:rule/{config.eventbridge_rule_name}"


def _topic_policy(topic_arn: str, rule_arn: str, account_id: str) -> str:
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "DefaultOwnerAccess",
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": [
                        "SNS:GetTopicAttributes",
                        "SNS:SetTopicAttributes",
                        "SNS:AddPermission",
                        "SNS:RemovePermission",
                        "SNS:DeleteTopic",
                        "SNS:Subscribe",
                        "SNS:ListSubscriptionsByTopic",
                        "SNS:Publish",
                    ],
                    "Resource": topic_arn,
                    "Condition": {"StringEquals": {"AWS:SourceOwner": account_id}},
                },
                {
                    "Sid": "AllowEventBridgeAlarmRulePublish",
                    "Effect": "Allow",
                    "Principal": {"Service": "events.amazonaws.com"},
                    "Action": "sns:Publish",
                    "Resource": topic_arn,
                    "Condition": {
                        "ArnEquals": {"aws:SourceArn": rule_arn},
                        "StringEquals": {"aws:SourceAccount": account_id},
                    },
                }
            ],
        }
    )


def _subscription_exists(sns, topic_arn: str, email: str) -> bool:
    paginator = sns.get_paginator("list_subscriptions_by_topic")
    for page in paginator.paginate(TopicArn=topic_arn):
        for item in page.get("Subscriptions", []):
            if item.get("Protocol") == "email" and item.get("Endpoint") == email:
                return True
    return False


def create_alarm_notifications() -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    account_id = clients.session.client("sts").get_caller_identity()["Account"]
    topic_response = clients.sns.create_topic(
        Name=config.alarm_sns_topic_name,
        Tags=[{"Key": item["Key"], "Value": item["Value"]} for item in config.tags],
    )
    topic_arn = topic_response["TopicArn"]
    rule_arn = _eventbridge_rule_arn(config, account_id)
    clients.sns.set_topic_attributes(
        TopicArn=topic_arn,
        AttributeName="Policy",
        AttributeValue=_topic_policy(topic_arn, rule_arn, account_id),
    )
    subscription_status = "existing"
    if not _subscription_exists(clients.sns, topic_arn, config.alarm_email):
        subscribe_response = clients.sns.subscribe(
            TopicArn=topic_arn,
            Protocol="email",
            Endpoint=config.alarm_email,
            ReturnSubscriptionArn=True,
        )
        subscription_status = str(subscribe_response.get("SubscriptionArn") or "pending_confirmation")
    payload = {
        "topic_name": config.alarm_sns_topic_name,
        "topic_arn": topic_arn,
        "email": config.alarm_email,
        "subscription_status": subscription_status,
        "eventbridge_rule_name": config.eventbridge_rule_name,
        "eventbridge_rule_arn": rule_arn,
        "note": (
            "SNS email subscriptions require the recipient to confirm the subscription email "
            "before notifications are delivered."
        ),
    }
    write_metadata(config, "alarm_notifications", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(create_alarm_notifications(), indent=2, default=str))


if __name__ == "__main__":
    main()
