"""Create an EventBridge cron fallback for Batch Data Quality monitoring."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    class ClientError(Exception):
        response = {"Error": {"Code": "Unknown"}}

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata
from .create_custom_data_quality_schedule import (
    _lambda_write_with_retries,
    _validate_eventbridge_schedule_expression,
    _wait_for_lambda_ready,
    _zip_lambda,
)
from .custom_data_quality_job import (
    custom_data_quality_environment,
    select_custom_data_quality_compute,
    upload_custom_data_quality_code,
)
from .custom_model_quality_job import sklearn_processing_image_uri


def _lambda_environment(config, *, image_uri: str, instance_type: str, code_s3_uri: str) -> dict[str, str]:
    environment = {
        **custom_data_quality_environment(
            config,
            baseline_data_s3_uri=config.baseline_monitor_s3_uri,
            current_data_s3_uri=config.batch_transform_input_s3_uri,
            data_capture_s3_uri=config.batch_data_capture_s3_uri,
            metric_name=config.batch_violations_metric_name,
            metric_dimension_name="BatchMonitoringSchedule",
            metric_dimension_value=config.batch_monitoring_schedule_name,
            endpoint_name=config.sagemaker_batch_model_name,
        ),
        "SAGEMAKER_EXECUTION_ROLE_ARN": config.sagemaker_execution_role_arn,
        "PROCESSING_IMAGE_URI": image_uri,
        "PROCESSING_INSTANCE_TYPE": instance_type,
        "PROCESSING_VOLUME_SIZE_GB": "20",
        "CODE_S3_URI": code_s3_uri,
        "REPORTS_S3_URI": config.custom_batch_data_quality_reports_s3_uri,
        "JOB_PREFIX": f"{config.resource_prefix}-custom-batch-data-quality",
        "MAX_RUNTIME_SECONDS": "1800",
    }
    environment.pop("AWS_REGION", None)
    return {key: value for key, value in environment.items() if value}


def _lambda_exists(clients, function_name: str) -> bool:
    try:
        clients.lambda_client.get_function(FunctionName=function_name)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            return False
        raise


def _upsert_lambda(clients, config, *, image_uri: str, instance_type: str, code_s3_uri: str) -> str:
    if not config.lambda_execution_role_arn:
        raise RuntimeError("LAMBDA_EXECUTION_ROLE_ARN is required to create the custom Batch Data Quality trigger.")
    source = Path("lambdas/custom_data_quality_trigger.py")
    zip_path = _zip_lambda(source, config.local_outputs_dir / f"{config.custom_batch_data_quality_trigger_lambda_name}.zip")
    code = zip_path.read_bytes()
    environment = {"Variables": _lambda_environment(config, image_uri=image_uri, instance_type=instance_type, code_s3_uri=code_s3_uri)}
    if _lambda_exists(clients, config.custom_batch_data_quality_trigger_lambda_name):
        _wait_for_lambda_ready(clients, config.custom_batch_data_quality_trigger_lambda_name)
        _lambda_write_with_retries(
            clients,
            label="UpdateFunctionCode",
            function_name=config.custom_batch_data_quality_trigger_lambda_name,
            call=clients.lambda_client.update_function_code,
            FunctionName=config.custom_batch_data_quality_trigger_lambda_name,
            ZipFile=code,
            Publish=True,
        )
        _wait_for_lambda_ready(clients, config.custom_batch_data_quality_trigger_lambda_name)
        _lambda_write_with_retries(
            clients,
            label="UpdateFunctionConfiguration",
            function_name=config.custom_batch_data_quality_trigger_lambda_name,
            call=clients.lambda_client.update_function_configuration,
            FunctionName=config.custom_batch_data_quality_trigger_lambda_name,
            Runtime="python3.12",
            Role=config.lambda_execution_role_arn,
            Handler="lambda_function.handler",
            Timeout=60,
            MemorySize=256,
            Environment=environment,
        )
        description = _wait_for_lambda_ready(clients, config.custom_batch_data_quality_trigger_lambda_name)
        return str(description["FunctionArn"])

    response = clients.lambda_client.create_function(
        FunctionName=config.custom_batch_data_quality_trigger_lambda_name,
        Runtime="python3.12",
        Role=config.lambda_execution_role_arn,
        Handler="lambda_function.handler",
        Code={"ZipFile": code},
        Timeout=60,
        MemorySize=256,
        Environment=environment,
        Tags={item["Key"]: item["Value"] for item in config.tags},
    )
    _wait_for_lambda_ready(clients, config.custom_batch_data_quality_trigger_lambda_name)
    return str(response["FunctionArn"])


def _allow_eventbridge_to_invoke_lambda(clients, config, *, function_arn: str, rule_arn: str) -> None:
    statement_id = f"{config.custom_batch_data_quality_schedule_name}-invoke"
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


def create_custom_batch_data_quality_schedule(
    *,
    if_native_unavailable: bool = False,
    force: bool = False,
) -> dict[str, object]:
    config = load_config(validate=True, require_execution_role=True)
    if if_native_unavailable and not force:
        native_metadata = read_metadata(config, "batch_monitoring_schedule")
        native_status = str(native_metadata.get("status") or "")
        if native_status != "native_batch_schedule_unavailable":
            payload = {
                "skipped": True,
                "reason": "native_batch_monitoring_schedule_available",
                "native_status": native_status or "unknown",
            }
            write_metadata(config, "custom_batch_data_quality_schedule", payload)
            return payload

    _validate_eventbridge_schedule_expression(config.custom_batch_data_quality_cron_expression)
    clients = create_clients(config)
    processing_compute = select_custom_data_quality_compute(clients, config)
    code_s3_uri = upload_custom_data_quality_code(
        clients,
        config,
        code_s3_uri=config.custom_batch_data_quality_code_s3_uri,
    )
    image_uri = sklearn_processing_image_uri(config)
    function_arn = _upsert_lambda(
        clients,
        config,
        image_uri=image_uri,
        instance_type=processing_compute.selected_instance_type,
        code_s3_uri=code_s3_uri,
    )
    rule_response = clients.events.put_rule(
        Name=config.custom_batch_data_quality_schedule_name,
        ScheduleExpression=config.custom_batch_data_quality_cron_expression,
        State="ENABLED",
        Description="Fallback cron that starts a custom Batch Data Quality Processing Job.",
        Tags=[{"Key": item["Key"], "Value": item["Value"]} for item in config.tags],
    )
    rule_arn = str(rule_response["RuleArn"])
    _allow_eventbridge_to_invoke_lambda(clients, config, function_arn=function_arn, rule_arn=rule_arn)
    clients.events.put_targets(
        Rule=config.custom_batch_data_quality_schedule_name,
        Targets=[{"Id": "CustomBatchDataQualityTrigger", "Arn": function_arn}],
    )
    payload = {
        "status": "created",
        "schedule_name": config.custom_batch_data_quality_schedule_name,
        "schedule_expression": config.custom_batch_data_quality_cron_expression,
        "rule_arn": rule_arn,
        "trigger_lambda_name": config.custom_batch_data_quality_trigger_lambda_name,
        "trigger_lambda_arn": function_arn,
        "code_s3_uri": code_s3_uri,
        "image_uri": image_uri,
        "baseline_data_s3_uri": config.baseline_monitor_s3_uri,
        "current_data_s3_uri": config.batch_transform_input_s3_uri,
        "batch_data_capture_s3_uri": config.batch_data_capture_s3_uri,
        "reports_s3_uri": config.custom_batch_data_quality_reports_s3_uri,
        "custom_metric": {
            "namespace": config.metric_namespace,
            "metric_name": config.batch_violations_metric_name,
            "dimension": {"BatchMonitoringSchedule": config.batch_monitoring_schedule_name},
        },
        "compute_selection": processing_compute.to_dict(),
        "note": "EventBridge invokes Lambda; Lambda starts a SageMaker Processing Job over the configured batch input in S3.",
    }
    write_metadata(config, "custom_batch_data_quality_schedule", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--if-native-unavailable", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            create_custom_batch_data_quality_schedule(
                if_native_unavailable=args.if_native_unavailable,
                force=args.force,
            ),
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
