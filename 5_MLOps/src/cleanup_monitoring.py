"""Delete monitoring resources created by the lab."""

from __future__ import annotations

import argparse
import json

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    class ClientError(Exception):
        response = {"Error": {"Code": "Unknown"}}

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata


def _delete_schedule_if_present(clients, name: str, actions: list[dict[str, str]]) -> None:
    if not name:
        return
    if any(action.get("resource") == name for action in actions):
        return
    try:
        clients.sagemaker.delete_monitoring_schedule(MonitoringScheduleName=name)
        actions.append({"resource": name, "status": "deleted"})
    except ClientError as exc:
        actions.append({"resource": name, "status": "not_deleted", "detail": exc.response.get("Error", {}).get("Code", "")})


def _delete_data_quality_job_definition_if_present(clients, name: str, actions: list[dict[str, str]]) -> None:
    if not name:
        return
    if any(action.get("resource") == name for action in actions):
        return
    try:
        clients.sagemaker.delete_data_quality_job_definition(JobDefinitionName=name)
        actions.append({"resource": name, "status": "deleted"})
    except ClientError as exc:
        actions.append({"resource": name, "status": "not_deleted", "detail": exc.response.get("Error", {}).get("Code", "")})


def _delete_model_quality_job_definition_if_present(clients, name: str, actions: list[dict[str, str]]) -> None:
    if not name:
        return
    if any(action.get("resource") == name for action in actions):
        return
    try:
        clients.sagemaker.delete_model_quality_job_definition(JobDefinitionName=name)
        actions.append({"resource": name, "status": "deleted"})
    except ClientError as exc:
        actions.append({"resource": name, "status": "not_deleted", "detail": exc.response.get("Error", {}).get("Code", "")})


def _delete_event_rule_if_present(clients, name: str, target_ids: list[str], actions: list[dict[str, str]]) -> None:
    if not name:
        return
    try:
        if target_ids:
            clients.events.remove_targets(Rule=name, Ids=target_ids, Force=True)
        clients.events.delete_rule(Name=name, Force=True)
        actions.append({"resource": name, "status": "deleted"})
    except ClientError as exc:
        actions.append({"resource": name, "status": "not_deleted", "detail": exc.response.get("Error", {}).get("Code", "")})


def _delete_lambda_if_present(clients, name: str, actions: list[dict[str, str]]) -> None:
    if not name:
        return
    try:
        clients.lambda_client.delete_function(FunctionName=name)
        actions.append({"resource": name, "status": "deleted"})
    except ClientError as exc:
        actions.append({"resource": name, "status": "not_deleted", "detail": exc.response.get("Error", {}).get("Code", "")})


def _delete_log_group_if_present(clients, name: str, actions: list[dict[str, str]]) -> None:
    if not name:
        return
    try:
        clients.logs.delete_log_group(logGroupName=name)
        actions.append({"resource": name, "status": "deleted"})
    except ClientError as exc:
        actions.append({"resource": name, "status": "not_deleted", "detail": exc.response.get("Error", {}).get("Code", "")})


def _delete_sns_topic_if_present(clients, topic_arn: str, actions: list[dict[str, str]]) -> None:
    if not topic_arn:
        return
    try:
        clients.sns.delete_topic(TopicArn=topic_arn)
        actions.append({"resource": topic_arn, "status": "deleted"})
    except ClientError as exc:
        actions.append({"resource": topic_arn, "status": "not_deleted", "detail": exc.response.get("Error", {}).get("Code", "")})


def cleanup_monitoring(delete_s3_outputs: bool = False) -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    actions = []
    stored_monitoring = read_metadata(config, "monitoring_schedule")
    stored_model_quality = read_metadata(config, "model_quality_schedule")
    stored_notifications = read_metadata(config, "alarm_notifications")
    _delete_schedule_if_present(clients, config.monitoring_schedule_name, actions)
    _delete_schedule_if_present(clients, str(stored_monitoring.get("actual_monitoring_schedule_name") or ""), actions)
    _delete_schedule_if_present(clients, config.model_quality_schedule_name, actions)
    _delete_schedule_if_present(clients, str(stored_model_quality.get("actual_model_quality_schedule_name") or ""), actions)
    _delete_schedule_if_present(clients, config.batch_monitoring_schedule_name, actions)
    _delete_data_quality_job_definition_if_present(
        clients,
        str(stored_monitoring.get("data_quality_job_definition_name") or ""),
        actions,
    )
    _delete_model_quality_job_definition_if_present(
        clients,
        str(stored_model_quality.get("model_quality_job_definition_name") or config.model_quality_job_definition_name),
        actions,
    )
    alarm_names = list(
        dict.fromkeys(
            [
                config.alarm_name,
                config.custom_data_quality_alarm_name,
                config.custom_batch_data_quality_alarm_name,
                config.model_quality_alarm_name,
                config.custom_model_quality_alarm_name,
                "mlops-drift-alarm",
            ]
        )
    )
    try:
        clients.cloudwatch.delete_alarms(AlarmNames=alarm_names)
        for alarm_name in alarm_names:
            actions.append({"resource": alarm_name, "status": "deleted"})
    except ClientError as exc:
        for alarm_name in alarm_names:
            actions.append({"resource": alarm_name, "status": "not_deleted", "detail": exc.response.get("Error", {}).get("Code", "")})

    _delete_event_rule_if_present(
        clients,
        config.custom_model_quality_schedule_name,
        ["CustomModelQualityTrigger"],
        actions,
    )
    _delete_lambda_if_present(clients, config.custom_model_quality_trigger_lambda_name, actions)
    _delete_log_group_if_present(clients, f"/aws/lambda/{config.custom_model_quality_trigger_lambda_name}", actions)
    _delete_event_rule_if_present(
        clients,
        config.custom_data_quality_schedule_name,
        ["CustomDataQualityTrigger"],
        actions,
    )
    _delete_lambda_if_present(clients, config.custom_data_quality_trigger_lambda_name, actions)
    _delete_log_group_if_present(clients, f"/aws/lambda/{config.custom_data_quality_trigger_lambda_name}", actions)
    _delete_event_rule_if_present(
        clients,
        config.custom_batch_data_quality_schedule_name,
        ["CustomBatchDataQualityTrigger"],
        actions,
    )
    _delete_lambda_if_present(clients, config.custom_batch_data_quality_trigger_lambda_name, actions)
    _delete_log_group_if_present(clients, f"/aws/lambda/{config.custom_batch_data_quality_trigger_lambda_name}", actions)
    _delete_sns_topic_if_present(clients, str(stored_notifications.get("topic_arn") or ""), actions)

    payload = {
        "actions": actions,
        "s3_outputs_deleted": delete_s3_outputs,
        "s3_note": "S3 lab artifacts are deleted by src.cleanup_s3_artifacts when cleanup_all runs with delete_s3_outputs=true.",
        "delete_s3_outputs_requested": delete_s3_outputs,
    }
    write_metadata(config, "cleanup_monitoring", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete-s3-outputs", action="store_true")
    args = parser.parse_args()
    print(json.dumps(cleanup_monitoring(delete_s3_outputs=args.delete_s3_outputs), indent=2))


if __name__ == "__main__":
    main()
