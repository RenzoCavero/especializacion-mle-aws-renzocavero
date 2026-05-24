"""Delete SageMaker pipeline, registry and terminal jobs created by the lab."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from typing import Any

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    class ClientError(Exception):
        response = {"Error": {"Code": "Unknown"}}

from .aws_clients import create_clients
from .config import load_config, read_metadata, write_metadata


TERMINAL_PROCESSING = {"Completed", "Failed", "Stopped"}
TERMINAL_TRAINING = {"Completed", "Failed", "Stopped"}
TERMINAL_TRANSFORM = {"Completed", "Failed", "Stopped"}


def _client_error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


def _name_from_arn(arn: str) -> str:
    return arn.rsplit("/", 1)[-1].strip()


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _job_names_from_metadata(config) -> dict[str, list[str]]:
    processing: list[str] = []
    training: list[str] = []
    transform: list[str] = []

    for metadata_name in [
        "baseline",
        "model_quality_baseline",
        "custom_data_quality_job",
        "custom_model_quality_job",
        "custom_batch_data_quality_job",
    ]:
        data = read_metadata(config, metadata_name)
        _append_unique(processing, str(data.get("baseline_job_name") or data.get("job_name") or ""))
        description = data.get("processing_job_description", {})
        if isinstance(description, dict):
            _append_unique(processing, str(description.get("ProcessingJobName") or ""))

    for metadata_name in [
        "data_quality_alarm_simulation",
        "model_quality_alarm_simulation",
        "batch_data_quality_alarm_simulation",
    ]:
        data = read_metadata(config, metadata_name)
        for value in data.values():
            if isinstance(value, dict):
                _append_unique(processing, str(value.get("job_name") or ""))
                description = value.get("processing_job_description", {})
                if isinstance(description, dict):
                    _append_unique(processing, str(description.get("ProcessingJobName") or ""))

    batch = read_metadata(config, "batch_transform")
    _append_unique(transform, str(batch.get("transform_job_name") or ""))
    description = batch.get("description", {})
    if isinstance(description, dict):
        _append_unique(transform, str(description.get("TransformJobName") or ""))

    steps = read_metadata(config, "pipeline_execution_status").get("steps", [])
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            metadata = step.get("Metadata", {})
            if not isinstance(metadata, dict):
                continue
            processing_arn = metadata.get("ProcessingJob", {}).get("Arn", "")
            training_arn = metadata.get("TrainingJob", {}).get("Arn", "")
            if processing_arn:
                _append_unique(processing, _name_from_arn(str(processing_arn)))
            if training_arn:
                _append_unique(training, _name_from_arn(str(training_arn)))

    return {"processing": processing, "training": training, "transform": transform}


def _pipeline_execution_job_names(clients, config) -> dict[str, list[str]]:
    processing: list[str] = []
    training: list[str] = []
    transform: list[str] = []
    try:
        paginator = clients.sagemaker.get_paginator("list_pipeline_executions")
        pages = paginator.paginate(PipelineName=config.pipeline_name)
    except Exception:
        return {"processing": processing, "training": training, "transform": transform}

    for page in pages:
        for summary in page.get("PipelineExecutionSummaries", []):
            execution_arn = str(summary.get("PipelineExecutionArn") or "")
            if not execution_arn:
                continue
            try:
                steps = clients.sagemaker.list_pipeline_execution_steps(PipelineExecutionArn=execution_arn)
            except ClientError:
                continue
            for step in steps.get("PipelineExecutionSteps", []):
                metadata = step.get("Metadata", {}) if isinstance(step, dict) else {}
                if not isinstance(metadata, dict):
                    continue
                processing_arn = metadata.get("ProcessingJob", {}).get("Arn", "")
                training_arn = metadata.get("TrainingJob", {}).get("Arn", "")
                if processing_arn:
                    _append_unique(processing, _name_from_arn(str(processing_arn)))
                if training_arn:
                    _append_unique(training, _name_from_arn(str(training_arn)))
    return {"processing": processing, "training": training, "transform": transform}


def _list_named_jobs(clients, *, list_method: str, name_key: str, status_key: str, name_contains: str) -> list[str]:
    names: list[str] = []
    try:
        paginator = clients.sagemaker.get_paginator(list_method)
        pages = paginator.paginate(NameContains=name_contains)
    except Exception:
        call = getattr(clients.sagemaker, list_method, None)
        if call is None:
            return names
        try:
            pages = [call(NameContains=name_contains)]
        except Exception:
            return names
    for page in pages:
        for item in page.get(status_key, []):
            _append_unique(names, str(item.get(name_key) or ""))
    return names


def _discover_lab_jobs(clients, config) -> dict[str, list[str]]:
    names = _job_names_from_metadata(config)
    from_pipeline = _pipeline_execution_job_names(clients, config)
    for key in names:
        for value in from_pipeline.get(key, []):
            _append_unique(names[key], value)

    for value in _list_named_jobs(
        clients,
        list_method="list_processing_jobs",
        name_key="ProcessingJobName",
        status_key="ProcessingJobSummaries",
        name_contains=config.resource_prefix,
    ):
        _append_unique(names["processing"], value)
    for value in _list_named_jobs(
        clients,
        list_method="list_transform_jobs",
        name_key="TransformJobName",
        status_key="TransformJobSummaries",
        name_contains=config.resource_prefix,
    ):
        _append_unique(names["transform"], value)
    return names


def _delete_processing_job(clients, name: str) -> dict[str, str]:
    try:
        description = clients.sagemaker.describe_processing_job(ProcessingJobName=name)
        status = str(description.get("ProcessingJobStatus") or "")
        if status not in TERMINAL_PROCESSING:
            clients.sagemaker.stop_processing_job(ProcessingJobName=name)
            return {"resource": name, "type": "processing_job", "status": "stop_requested", "previous_status": status}
        clients.sagemaker.delete_processing_job(ProcessingJobName=name)
        return {"resource": name, "type": "processing_job", "status": "deleted", "previous_status": status}
    except AttributeError:
        return {"resource": name, "type": "processing_job", "status": "not_supported"}
    except ClientError as exc:
        return {"resource": name, "type": "processing_job", "status": "not_deleted", "detail": _client_error_code(exc)}


def _delete_training_job(clients, name: str) -> dict[str, str]:
    try:
        description = clients.sagemaker.describe_training_job(TrainingJobName=name)
        status = str(description.get("TrainingJobStatus") or "")
        if status not in TERMINAL_TRAINING:
            clients.sagemaker.stop_training_job(TrainingJobName=name)
            return {"resource": name, "type": "training_job", "status": "stop_requested", "previous_status": status}
        clients.sagemaker.delete_training_job(TrainingJobName=name)
        return {"resource": name, "type": "training_job", "status": "deleted", "previous_status": status}
    except AttributeError:
        return {"resource": name, "type": "training_job", "status": "not_supported"}
    except ClientError as exc:
        return {"resource": name, "type": "training_job", "status": "not_deleted", "detail": _client_error_code(exc)}


def _delete_transform_job(clients, name: str) -> dict[str, str]:
    try:
        description = clients.sagemaker.describe_transform_job(TransformJobName=name)
        status = str(description.get("TransformJobStatus") or "")
        if status not in TERMINAL_TRANSFORM:
            clients.sagemaker.stop_transform_job(TransformJobName=name)
            return {"resource": name, "type": "transform_job", "status": "stop_requested", "previous_status": status}
        clients.sagemaker.delete_transform_job(TransformJobName=name)
        return {"resource": name, "type": "transform_job", "status": "deleted", "previous_status": status}
    except AttributeError:
        return {"resource": name, "type": "transform_job", "status": "not_supported"}
    except ClientError as exc:
        return {"resource": name, "type": "transform_job", "status": "not_deleted", "detail": _client_error_code(exc)}


def _delete_pipeline(clients, config) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    try:
        executions = clients.sagemaker.list_pipeline_executions(PipelineName=config.pipeline_name)
    except ClientError as exc:
        actions.append({"resource": config.pipeline_name, "type": "pipeline", "status": "not_found", "detail": _client_error_code(exc)})
        return actions

    for summary in executions.get("PipelineExecutionSummaries", []):
        execution_arn = str(summary.get("PipelineExecutionArn") or "")
        status = str(summary.get("PipelineExecutionStatus") or "")
        if execution_arn and status in {"Executing", "Stopping"}:
            try:
                clients.sagemaker.stop_pipeline_execution(PipelineExecutionArn=execution_arn)
                actions.append({"resource": execution_arn, "type": "pipeline_execution", "status": "stop_requested"})
            except ClientError as exc:
                actions.append({"resource": execution_arn, "type": "pipeline_execution", "status": "not_stopped", "detail": _client_error_code(exc)})

    for _ in range(12):
        try:
            executions = clients.sagemaker.list_pipeline_executions(PipelineName=config.pipeline_name)
        except ClientError:
            break
        running = [
            item
            for item in executions.get("PipelineExecutionSummaries", [])
            if str(item.get("PipelineExecutionStatus") or "") in {"Executing", "Stopping"}
        ]
        if not running:
            break
        time.sleep(10)

    try:
        response = clients.sagemaker.delete_pipeline(
            PipelineName=config.pipeline_name,
            ClientRequestToken=uuid.uuid4().hex,
        )
        actions.append({"resource": config.pipeline_name, "type": "pipeline", "status": "deleted", "arn": str(response.get("PipelineArn", ""))})
    except ClientError as exc:
        actions.append({"resource": config.pipeline_name, "type": "pipeline", "status": "not_deleted", "detail": _client_error_code(exc)})
    return actions


def _delete_model_package_group(clients, config, *, include_external: bool) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if config.is_integrated and not include_external:
        return [
            {
                "resource": config.model_package_group_name,
                "type": "model_package_group",
                "status": "skipped",
                "reason": "integrated_mode protects external registry resources by default",
            }
        ]
    try:
        paginator = clients.sagemaker.get_paginator("list_model_packages")
        pages = paginator.paginate(ModelPackageGroupName=config.model_package_group_name)
    except ClientError as exc:
        return [{"resource": config.model_package_group_name, "type": "model_package_group", "status": "not_found", "detail": _client_error_code(exc)}]
    except Exception as exc:
        return [
            {
                "resource": config.model_package_group_name,
                "type": "model_package_group",
                "status": "not_listed",
                "detail": exc.__class__.__name__,
            }
        ]

    package_arns: list[str] = []
    for page in pages:
        for item in page.get("ModelPackageSummaryList", []):
            _append_unique(package_arns, str(item.get("ModelPackageArn") or ""))
    for arn in package_arns:
        try:
            clients.sagemaker.delete_model_package(ModelPackageName=arn)
            actions.append({"resource": arn, "type": "model_package", "status": "deleted"})
        except ClientError as exc:
            actions.append({"resource": arn, "type": "model_package", "status": "not_deleted", "detail": _client_error_code(exc)})
    try:
        clients.sagemaker.delete_model_package_group(ModelPackageGroupName=config.model_package_group_name)
        actions.append({"resource": config.model_package_group_name, "type": "model_package_group", "status": "deleted"})
    except ClientError as exc:
        actions.append({"resource": config.model_package_group_name, "type": "model_package_group", "status": "not_deleted", "detail": _client_error_code(exc)})
    return actions


def _delete_log_group_if_present(clients, name: str) -> dict[str, str]:
    try:
        clients.logs.delete_log_group(logGroupName=name)
        return {"resource": name, "type": "log_group", "status": "deleted"}
    except ClientError as exc:
        return {"resource": name, "type": "log_group", "status": "not_deleted", "detail": _client_error_code(exc)}


def _delete_job_log_streams(clients, *, log_group: str, job_names: list[str]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for job_name in job_names:
        try:
            paginator = clients.logs.get_paginator("describe_log_streams")
            pages = paginator.paginate(logGroupName=log_group, logStreamNamePrefix=job_name)
        except ClientError as exc:
            actions.append({"resource": f"{log_group}:{job_name}", "type": "log_stream", "status": "not_listed", "detail": _client_error_code(exc)})
            continue
        except Exception:
            try:
                pages = [clients.logs.describe_log_streams(logGroupName=log_group, logStreamNamePrefix=job_name)]
            except ClientError as exc:
                actions.append({"resource": f"{log_group}:{job_name}", "type": "log_stream", "status": "not_listed", "detail": _client_error_code(exc)})
                continue
            except Exception as exc:
                actions.append({"resource": f"{log_group}:{job_name}", "type": "log_stream", "status": "not_listed", "detail": exc.__class__.__name__})
                continue
        for page in pages:
            for stream in page.get("logStreams", []):
                stream_name = str(stream.get("logStreamName") or "")
                if not stream_name:
                    continue
                try:
                    clients.logs.delete_log_stream(logGroupName=log_group, logStreamName=stream_name)
                    actions.append({"resource": f"{log_group}:{stream_name}", "type": "log_stream", "status": "deleted"})
                except ClientError as exc:
                    actions.append({"resource": f"{log_group}:{stream_name}", "type": "log_stream", "status": "not_deleted", "detail": _client_error_code(exc)})
    return actions


def cleanup_sagemaker_resources(*, include_external: bool = False) -> dict[str, object]:
    config = load_config(validate=True)
    clients = create_clients(config)
    jobs = _discover_lab_jobs(clients, config)
    actions: list[dict[str, str]] = []

    actions.extend(_delete_pipeline(clients, config))
    for name in jobs["processing"]:
        actions.append(_delete_processing_job(clients, name))
    for name in jobs["training"]:
        actions.append(_delete_training_job(clients, name))
    for name in jobs["transform"]:
        actions.append(_delete_transform_job(clients, name))
    actions.extend(_delete_model_package_group(clients, config, include_external=include_external))

    log_actions: list[dict[str, str]] = []
    log_actions.extend(_delete_job_log_streams(clients, log_group="/aws/sagemaker/ProcessingJobs", job_names=jobs["processing"]))
    log_actions.extend(_delete_job_log_streams(clients, log_group="/aws/sagemaker/TrainingJobs", job_names=jobs["training"]))
    log_actions.extend(_delete_job_log_streams(clients, log_group="/aws/sagemaker/TransformJobs", job_names=jobs["transform"]))
    log_actions.append(_delete_log_group_if_present(clients, f"/aws/sagemaker/Endpoints/{config.endpoint_name}"))

    payload = {
        "actions": actions,
        "log_actions": log_actions,
        "discovered_jobs": jobs,
        "include_external": include_external,
        "note": (
            "SageMaker jobs can be deleted only when terminal. Running jobs are stopped first and may require "
            "a second cleanup pass after they reach Stopped."
        ),
    }
    write_metadata(config, "cleanup_sagemaker_resources", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-external", action="store_true")
    args = parser.parse_args()
    print(json.dumps(cleanup_sagemaker_resources(include_external=args.include_external), indent=2, default=str))


if __name__ == "__main__":
    main()
