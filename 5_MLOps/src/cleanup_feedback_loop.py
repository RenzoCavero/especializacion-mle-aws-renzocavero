"""Delete EventBridge, Step Functions and Lambda resources created by the lab."""

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


def cleanup_feedback_loop() -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    actions = []

    try:
        clients.events.remove_targets(Rule=config.eventbridge_rule_name, Ids=["MLOpsFeedbackLoop"], Force=True)
        actions.append({"resource": config.eventbridge_rule_name, "operation": "remove_targets", "status": "ok"})
    except ClientError as exc:
        actions.append({"resource": config.eventbridge_rule_name, "operation": "remove_targets", "status": "not_deleted", "detail": exc.response.get("Error", {}).get("Code", "")})
    try:
        clients.events.delete_rule(Name=config.eventbridge_rule_name, Force=True)
        actions.append({"resource": config.eventbridge_rule_name, "operation": "delete_rule", "status": "ok"})
    except ClientError as exc:
        actions.append({"resource": config.eventbridge_rule_name, "operation": "delete_rule", "status": "not_deleted", "detail": exc.response.get("Error", {}).get("Code", "")})

    feedback = read_metadata(config, "feedback_loop")
    state_machine_arn = feedback.get("state_machine_arn")
    if state_machine_arn:
        try:
            clients.stepfunctions.delete_state_machine(stateMachineArn=str(state_machine_arn))
            actions.append({"resource": state_machine_arn, "operation": "delete_state_machine", "status": "ok"})
        except ClientError as exc:
            actions.append({"resource": state_machine_arn, "operation": "delete_state_machine", "status": "not_deleted", "detail": exc.response.get("Error", {}).get("Code", "")})

    for function_name in [
        config.feedback_lambda_name,
        config.retraining_lambda_name,
        config.rollback_lambda_name,
        config.baseline_update_lambda_name,
        config.human_review_lambda_name,
    ]:
        try:
            clients.lambda_client.delete_function(FunctionName=function_name)
            actions.append({"resource": function_name, "operation": "delete_function", "status": "ok"})
        except ClientError as exc:
            actions.append({"resource": function_name, "operation": "delete_function", "status": "not_deleted", "detail": exc.response.get("Error", {}).get("Code", "")})
        try:
            clients.logs.delete_log_group(logGroupName=f"/aws/lambda/{function_name}")
            actions.append({"resource": f"/aws/lambda/{function_name}", "operation": "delete_log_group", "status": "ok"})
        except ClientError as exc:
            actions.append({"resource": f"/aws/lambda/{function_name}", "operation": "delete_log_group", "status": "not_deleted", "detail": exc.response.get("Error", {}).get("Code", "")})

    payload = {"actions": actions}
    write_metadata(config, "cleanup_feedback_loop", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(cleanup_feedback_loop(), indent=2, default=str))


if __name__ == "__main__":
    main()
