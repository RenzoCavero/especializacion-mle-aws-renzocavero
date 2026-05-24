"""Create Lambda functions and Step Functions state machine for feedback loop."""

from __future__ import annotations

import argparse
import json
import time
import zipfile
from pathlib import Path

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    class ClientError(Exception):
        response = {"Error": {"Code": "Unknown"}}

from .aws_clients import create_clients
from .config import load_config, write_metadata


LAMBDA_SOURCES = {
    "feedback": ("lambdas/feedback_handler/lambda_function.py", "feedback_lambda_name"),
    "retraining": ("lambdas/retraining_trigger/lambda_function.py", "retraining_lambda_name"),
    "rollback": ("lambdas/rollback_handler/lambda_function.py", "rollback_lambda_name"),
    "baseline_update": ("lambdas/baseline_update_handler/lambda_function.py", "baseline_update_lambda_name"),
    "human_review": ("lambdas/human_review_handler/lambda_function.py", "human_review_lambda_name"),
}
LAMBDA_UPDATE_RETRYABLE_ERRORS = {"ResourceConflictException", "TooManyRequestsException"}


def _client_error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


def _zip_lambda(source_path: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(source_path, "lambda_function.py")
    return output_path


def _lambda_exists(clients, function_name: str) -> bool:
    try:
        clients.lambda_client.get_function(FunctionName=function_name)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return False
        raise


def _wait_for_lambda_ready(clients, function_name: str, *, timeout_seconds: int = 180, poll_seconds: int = 5) -> dict[str, object]:
    started_at = time.monotonic()
    while True:
        description = clients.lambda_client.get_function_configuration(FunctionName=function_name)
        state = str(description.get("State") or "Unknown")
        last_update = str(description.get("LastUpdateStatus") or "Successful")
        if state == "Active" and last_update == "Successful":
            return description
        if state == "Failed" or last_update == "Failed":
            reason = description.get("StateReason") or description.get("LastUpdateStatusReason") or ""
            raise RuntimeError(f"Lambda {function_name} is {state}/{last_update}: {reason}")
        elapsed = int(time.monotonic() - started_at)
        if elapsed >= timeout_seconds:
            raise TimeoutError(f"Lambda {function_name} is still {state}/{last_update} after {elapsed}s.")
        print(f"Lambda {function_name} is {state}/{last_update}. Waiting {poll_seconds}s...")
        time.sleep(poll_seconds)


def _lambda_write_with_retries(clients, *, label: str, function_name: str, call, **kwargs):
    max_attempts = 6
    for attempt in range(1, max_attempts + 1):
        try:
            return call(**kwargs)
        except ClientError as exc:
            code = _client_error_code(exc)
            if code not in LAMBDA_UPDATE_RETRYABLE_ERRORS or attempt == max_attempts:
                raise
            print(f"{label} hit transient {code} for {function_name}. Waiting 10s before retry {attempt + 1}/{max_attempts}...")
            time.sleep(10)
            _wait_for_lambda_ready(clients, function_name)
    raise RuntimeError(f"{label} did not complete for {function_name}.")


def _upsert_lambda(clients, config, logical_name: str, source_path: str, function_name: str) -> str:
    zip_path = _zip_lambda(Path(source_path), config.local_outputs_dir / f"{function_name}.zip")
    code_bytes = zip_path.read_bytes()
    env = {
        "LAB_MODE": config.lab_mode,
        "PIPELINE_NAME": config.pipeline_name,
        "ENDPOINT_NAME": config.endpoint_name,
        "MODEL_PACKAGE_GROUP_NAME": config.model_package_group_name,
        "ENABLE_AUTOMATIC_RETRAINING": str(config.enable_automatic_retraining).lower(),
        "RESOURCE_PREFIX": config.resource_prefix,
        "ALARM_NAME": config.alarm_name,
        "DATA_QUALITY_ALARM_NAME": config.alarm_name,
        "CUSTOM_DATA_QUALITY_ALARM_NAME": config.custom_data_quality_alarm_name,
        "CUSTOM_BATCH_DATA_QUALITY_ALARM_NAME": config.custom_batch_data_quality_alarm_name,
        "MODEL_QUALITY_ALARM_NAME": config.model_quality_alarm_name,
        "CUSTOM_MODEL_QUALITY_ALARM_NAME": config.custom_model_quality_alarm_name,
        "VIOLATIONS_METRIC_NAME": config.violations_metric_name,
        "BATCH_VIOLATIONS_METRIC_NAME": config.batch_violations_metric_name,
        "MODEL_QUALITY_NATIVE_METRIC_NAME": config.model_quality_native_metric_name,
        "MODEL_QUALITY_F1_METRIC_NAME": config.model_quality_f1_metric_name,
        "ALARM_THRESHOLD": str(config.alarm_threshold),
        "MODEL_QUALITY_F1_THRESHOLD": str(config.model_quality_f1_threshold),
    }
    if _lambda_exists(clients, function_name):
        _wait_for_lambda_ready(clients, function_name)
        _lambda_write_with_retries(
            clients,
            label="UpdateFunctionCode",
            function_name=function_name,
            call=clients.lambda_client.update_function_code,
            FunctionName=function_name,
            ZipFile=code_bytes,
            Publish=True,
        )
        _wait_for_lambda_ready(clients, function_name)
        _lambda_write_with_retries(
            clients,
            label="UpdateFunctionConfiguration",
            function_name=function_name,
            call=clients.lambda_client.update_function_configuration,
            FunctionName=function_name,
            Role=config.lambda_execution_role_arn,
            Runtime="python3.11",
            Handler="lambda_function.lambda_handler",
            Timeout=60,
            Environment={"Variables": env},
        )
        _wait_for_lambda_ready(clients, function_name)
    else:
        clients.lambda_client.create_function(
            FunctionName=function_name,
            Runtime="python3.11",
            Role=config.lambda_execution_role_arn,
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": code_bytes},
            Description=f"MLOps lab {logical_name} handler.",
            Timeout=60,
            Environment={"Variables": env},
            Tags={item["Key"]: item["Value"] for item in config.tags},
            Publish=True,
        )
        _wait_for_lambda_ready(clients, function_name)
    desc = clients.lambda_client.get_function(FunctionName=function_name)
    return desc["Configuration"]["FunctionArn"]


def _render_asl(config, function_arns: dict[str, str]) -> str:
    template = Path("stepfunctions/feedback_loop.asl.json").read_text(encoding="utf-8")
    replacements = {
        "${FEEDBACK_HANDLER_LAMBDA_ARN}": function_arns["feedback"],
        "${RETRAINING_TRIGGER_LAMBDA_ARN}": function_arns["retraining"],
        "${ROLLBACK_HANDLER_LAMBDA_ARN}": function_arns["rollback"],
        "${BASELINE_UPDATE_HANDLER_LAMBDA_ARN}": function_arns["baseline_update"],
        "${HUMAN_REVIEW_HANDLER_LAMBDA_ARN}": function_arns["human_review"],
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    json.loads(template)
    return template


def create_feedback_loop() -> dict[str, object]:
    config = load_config(validate=True)
    if not config.enable_feedback_loop:
        payload = {"skipped": True, "reason": "ENABLE_FEEDBACK_LOOP=false"}
        write_metadata(config, "feedback_loop", payload)
        return payload
    config.require(["lambda_execution_role_arn", "stepfunctions_role_arn"])

    clients = create_clients(config)
    function_arns = {}
    for logical_name, (source, attr_name) in LAMBDA_SOURCES.items():
        function_arns[logical_name] = _upsert_lambda(clients, config, logical_name, source, getattr(config, attr_name))

    definition = _render_asl(config, function_arns)
    try:
        existing = clients.stepfunctions.list_state_machines()
        matches = [item for item in existing.get("stateMachines", []) if item["name"] == config.state_machine_name]
        if matches:
            state_machine_arn = matches[0]["stateMachineArn"]
            clients.stepfunctions.update_state_machine(
                stateMachineArn=state_machine_arn,
                definition=definition,
                roleArn=config.stepfunctions_role_arn,
            )
            action = "updated"
        else:
            response = clients.stepfunctions.create_state_machine(
                name=config.state_machine_name,
                definition=definition,
                roleArn=config.stepfunctions_role_arn,
                type="STANDARD",
                tags=[{"key": item["Key"], "value": item["Value"]} for item in config.tags],
            )
            state_machine_arn = response["stateMachineArn"]
            action = "created"
    except ClientError:
        raise

    payload = {
        "action": action,
        "state_machine_name": config.state_machine_name,
        "state_machine_arn": state_machine_arn,
        "lambda_functions": function_arns,
        "automatic_retraining_enabled": config.enable_automatic_retraining,
        "guardrail": "No loops: Step Functions has one action branch and no recursive transition.",
    }
    write_metadata(config, "feedback_loop", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(create_feedback_loop(), indent=2, default=str))


if __name__ == "__main__":
    main()
