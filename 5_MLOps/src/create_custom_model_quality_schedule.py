"""Create an EventBridge cron fallback that starts custom Model Quality jobs."""

from __future__ import annotations

import argparse
import json
import time
import zipfile
from pathlib import Path
from typing import Any

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    class ClientError(Exception):
        response = {"Error": {"Code": "Unknown"}}

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata
from .create_monitoring_schedule import validate_monitoring_schedule_expression
from .custom_model_quality_job import (
    custom_model_quality_environment,
    select_custom_model_quality_compute,
    sklearn_processing_image_uri,
    upload_custom_model_quality_code,
)


LAMBDA_UPDATE_RETRYABLE_ERRORS = {"ResourceConflictException", "TooManyRequestsException"}


def _client_error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


def _validate_eventbridge_schedule_expression(expression: str) -> None:
    if expression.strip().upper() == "NOW":
        raise ValueError(
            "CUSTOM_MODEL_QUALITY_CRON_EXPRESSION must be a cron expression for EventBridge. "
            "Use `python -m src.start_custom_model_quality_job --wait` for a manual run."
        )
    validate_monitoring_schedule_expression(expression)


def _zip_lambda(source_path: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(source_path, "lambda_function.py")
    return output_path


def _lambda_environment(config, *, image_uri: str, instance_type: str, code_s3_uri: str) -> dict[str, str]:
    environment = {
        **custom_model_quality_environment(config),
        "SAGEMAKER_EXECUTION_ROLE_ARN": config.sagemaker_execution_role_arn,
        "PROCESSING_IMAGE_URI": image_uri,
        "PROCESSING_INSTANCE_TYPE": instance_type,
        "PROCESSING_VOLUME_SIZE_GB": "20",
        "CODE_S3_URI": code_s3_uri,
        "REPORTS_S3_URI": config.custom_model_quality_reports_s3_uri,
        "JOB_PREFIX": f"{config.resource_prefix}-custom-model-quality",
        "MAX_RUNTIME_SECONDS": "1800",
    }
    # Lambda owns AWS_REGION as a reserved runtime variable. The trigger reads
    # that runtime value and passes it through to the Processing Job.
    environment.pop("AWS_REGION", None)
    return {key: value for key, value in environment.items() if value}


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


def _upsert_lambda(clients, config, *, image_uri: str, instance_type: str, code_s3_uri: str) -> str:
    if not config.lambda_execution_role_arn:
        raise RuntimeError("LAMBDA_EXECUTION_ROLE_ARN is required to create the custom Model Quality trigger.")
    source = Path("lambdas/custom_model_quality_trigger.py")
    zip_path = _zip_lambda(source, config.local_outputs_dir / f"{config.custom_model_quality_trigger_lambda_name}.zip")
    code = zip_path.read_bytes()
    environment = {"Variables": _lambda_environment(config, image_uri=image_uri, instance_type=instance_type, code_s3_uri=code_s3_uri)}
    try:
        response = clients.lambda_client.create_function(
            FunctionName=config.custom_model_quality_trigger_lambda_name,
            Runtime="python3.12",
            Role=config.lambda_execution_role_arn,
            Handler="lambda_function.handler",
            Code={"ZipFile": code},
            Timeout=60,
            MemorySize=256,
            Environment=environment,
            Tags={item["Key"]: item["Value"] for item in config.tags},
        )
        _wait_for_lambda_ready(clients, config.custom_model_quality_trigger_lambda_name)
        return str(response["FunctionArn"])
    except ClientError as exc:
        if _client_error_code(exc) != "ResourceConflictException":
            raise
        _wait_for_lambda_ready(clients, config.custom_model_quality_trigger_lambda_name)
        _lambda_write_with_retries(
            clients,
            label="UpdateFunctionCode",
            function_name=config.custom_model_quality_trigger_lambda_name,
            call=clients.lambda_client.update_function_code,
            FunctionName=config.custom_model_quality_trigger_lambda_name,
            ZipFile=code,
            Publish=True,
        )
        _wait_for_lambda_ready(clients, config.custom_model_quality_trigger_lambda_name)
        _lambda_write_with_retries(
            clients,
            label="UpdateFunctionConfiguration",
            function_name=config.custom_model_quality_trigger_lambda_name,
            call=clients.lambda_client.update_function_configuration,
            FunctionName=config.custom_model_quality_trigger_lambda_name,
            Runtime="python3.12",
            Role=config.lambda_execution_role_arn,
            Handler="lambda_function.handler",
            Timeout=60,
            MemorySize=256,
            Environment=environment,
        )
        description = _wait_for_lambda_ready(clients, config.custom_model_quality_trigger_lambda_name)
        return str(description["FunctionArn"])


def _allow_eventbridge_to_invoke_lambda(clients, config, *, function_arn: str, rule_arn: str) -> None:
    statement_id = f"{config.custom_model_quality_schedule_name}-invoke"
    try:
        clients.lambda_client.add_permission(
            FunctionName=function_arn,
            StatementId=statement_id[:100],
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
            SourceArn=rule_arn,
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ResourceConflictException":
            raise


def create_custom_model_quality_schedule(
    *,
    if_native_unavailable: bool = False,
    force: bool = False,
) -> dict[str, object]:
    config = load_config(validate=True, require_execution_role=True)
    if if_native_unavailable and not force:
        native_metadata = read_metadata(config, "model_quality_schedule")
        native_status = str(native_metadata.get("status") or "")
        if native_status != "native_model_quality_schedule_unavailable":
            payload = {
                "skipped": True,
                "reason": "native_model_quality_schedule_available",
                "native_status": native_status or "unknown",
            }
            write_metadata(config, "custom_model_quality_schedule", payload)
            return payload

    _validate_eventbridge_schedule_expression(config.custom_model_quality_cron_expression)
    clients = create_clients(config)
    processing_compute = select_custom_model_quality_compute(clients, config)
    code_s3_uri = upload_custom_model_quality_code(clients, config)
    image_uri = sklearn_processing_image_uri(config)
    function_arn = _upsert_lambda(
        clients,
        config,
        image_uri=image_uri,
        instance_type=processing_compute.selected_instance_type,
        code_s3_uri=code_s3_uri,
    )
    response = clients.events.put_rule(
        Name=config.custom_model_quality_schedule_name,
        ScheduleExpression=config.custom_model_quality_cron_expression,
        State="ENABLED",
        Description="Fallback cron that starts a custom Model Quality Processing Job.",
        Tags=[{"Key": item["Key"], "Value": item["Value"]} for item in config.tags],
    )
    rule_arn = str(response.get("RuleArn") or "")
    _allow_eventbridge_to_invoke_lambda(clients, config, function_arn=function_arn, rule_arn=rule_arn)
    clients.events.put_targets(
        Rule=config.custom_model_quality_schedule_name,
        Targets=[{"Id": "CustomModelQualityTrigger", "Arn": function_arn}],
    )
    payload = {
        "status": "created",
        "schedule_name": config.custom_model_quality_schedule_name,
        "schedule_expression": config.custom_model_quality_cron_expression,
        "rule_arn": rule_arn,
        "trigger_lambda_name": config.custom_model_quality_trigger_lambda_name,
        "trigger_lambda_arn": function_arn,
        "code_s3_uri": code_s3_uri,
        "image_uri": image_uri,
        "predictions_s3_uri": config.model_quality_predictions_s3_uri,
        "ground_truth_debug_s3_uri": config.model_quality_ground_truth_debug_s3_uri,
        "reports_s3_uri": config.custom_model_quality_reports_s3_uri,
        "custom_metric": {
            "namespace": config.metric_namespace,
            "f1_metric_name": config.model_quality_f1_metric_name,
            "dimension": {"EndpointName": config.endpoint_name},
        },
        "compute_selection": processing_compute.to_dict(),
        "note": "EventBridge invokes Lambda; Lambda starts a SageMaker Processing Job with a unique job name.",
    }
    write_metadata(config, "custom_model_quality_schedule", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--if-native-unavailable", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            create_custom_model_quality_schedule(
                if_native_unavailable=args.if_native_unavailable,
                force=args.force,
            ),
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
