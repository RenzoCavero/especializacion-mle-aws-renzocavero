from __future__ import annotations

import logging
from botocore.exceptions import ClientError

from src.aws_clients import client
from src.config import get_config
from src.logging_utils import configure_logging


LOGGER = logging.getLogger(__name__)


def delete_s3_batch(s3, bucket_name: str, objects: list[dict[str, str]], label: str) -> int:
    deleted = 0
    while objects:
        batch = objects[:1000]
        s3.delete_objects(Bucket=bucket_name, Delete={"Objects": batch})
        deleted += len(batch)
        LOGGER.info("Deleted %s %s S3 object(s) from %s", len(batch), label, bucket_name)
        objects = objects[1000:]
    return deleted


def delete_feature_group(config) -> None:
    sm = client(config, "sagemaker")
    try:
        sm.delete_feature_group(FeatureGroupName=config.feature_group_name)
        LOGGER.info("Requested deletion of Feature Group %s", config.feature_group_name)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"ResourceNotFound", "ValidationException"}:
            LOGGER.info("Feature Group %s does not exist or is already gone", config.feature_group_name)
            return
        raise


def delete_pipeline(config) -> None:
    sm = client(config, "sagemaker")
    for pipeline_name in (config.pipeline_name, config.hpo_pipeline_name):
        try:
            sm.delete_pipeline(PipelineName=pipeline_name)
            LOGGER.info("Deleted Pipeline %s", pipeline_name)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"ResourceNotFound", "ValidationException"}:
                continue
            raise


def delete_model_registry(config) -> None:
    sm = client(config, "sagemaker")
    for model in sm.list_models(NameContains=config.resource_prefix, MaxResults=100).get("Models", []):
        sm.delete_model(ModelName=model["ModelName"])
        LOGGER.info("Deleted SageMaker Model %s", model["ModelName"])
    try:
        packages = sm.list_model_packages(ModelPackageGroupName=config.model_package_group_name, MaxResults=100)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"ResourceNotFound", "ValidationException"}:
            return
        raise
    for package in packages.get("ModelPackageSummaryList", []):
        sm.delete_model_package(ModelPackageName=package["ModelPackageArn"])
        LOGGER.info("Deleted Model Package %s", package["ModelPackageArn"])
    try:
        sm.delete_model_package_group(ModelPackageGroupName=config.model_package_group_name)
        LOGGER.info("Deleted Model Package Group %s", config.model_package_group_name)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"ResourceNotFound", "ValidationException"}:
            raise


def delete_experiments(config) -> None:
    sm = client(config, "sagemaker")
    try:
        trials = sm.list_trials(ExperimentName=config.experiment_name, MaxResults=100)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"ResourceNotFound", "ValidationException"}:
            return
        raise
    for trial in trials.get("TrialSummaries", []):
        trial_name = trial["TrialName"]
        components = sm.list_trial_components(TrialName=trial_name, MaxResults=100)
        for component in components.get("TrialComponentSummaries", []):
            sm.disassociate_trial_component(TrialComponentName=component["TrialComponentName"], TrialName=trial_name)
        sm.delete_trial(TrialName=trial_name)
        LOGGER.info("Deleted Trial %s", trial_name)
    try:
        sm.delete_experiment(ExperimentName=config.experiment_name)
        LOGGER.info("Deleted Experiment %s", config.experiment_name)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"ResourceNotFound", "ValidationException"}:
            raise


def delete_s3_objects(config) -> int:
    s3 = client(config, "s3")
    total_deleted = 0

    try:
        version_paginator = s3.get_paginator("list_object_versions")
        for page in version_paginator.paginate(Bucket=config.s3_bucket_name):
            version_batch = []
            for item in page.get("Versions", []):
                version_batch.append({"Key": item["Key"], "VersionId": item["VersionId"]})
            for item in page.get("DeleteMarkers", []):
                version_batch.append({"Key": item["Key"], "VersionId": item["VersionId"]})
            total_deleted += delete_s3_batch(s3, config.s3_bucket_name, version_batch, "versioned")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"NoSuchBucket", "AccessDenied"}:
            if code == "NoSuchBucket":
                LOGGER.info("S3 bucket %s does not exist.", config.s3_bucket_name)
                return total_deleted
            raise

    paginator = s3.get_paginator("list_objects_v2")
    delete_batch = []
    try:
        for page in paginator.paginate(Bucket=config.s3_bucket_name):
            delete_batch = []
            for item in page.get("Contents", []):
                delete_batch.append({"Key": item["Key"]})
            total_deleted += delete_s3_batch(s3, config.s3_bucket_name, delete_batch, "current")
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "NoSuchBucket":
            LOGGER.info("S3 bucket %s does not exist.", config.s3_bucket_name)
            return total_deleted
        raise
    LOGGER.info("Deleted %s total S3 object(s) from %s", total_deleted, config.s3_bucket_name)
    return total_deleted


def stop_active_jobs(config) -> None:
    sm = client(config, "sagemaker")
    for job in sm.list_processing_jobs(StatusEquals="InProgress", NameContains=config.resource_prefix).get("ProcessingJobSummaries", []):
        sm.stop_processing_job(ProcessingJobName=job["ProcessingJobName"])
        LOGGER.info("Stopped Processing Job %s", job["ProcessingJobName"])
    for job in sm.list_training_jobs(StatusEquals="InProgress", NameContains=config.resource_prefix).get("TrainingJobSummaries", []):
        sm.stop_training_job(TrainingJobName=job["TrainingJobName"])
        LOGGER.info("Stopped Training Job %s", job["TrainingJobName"])
    for job in sm.list_hyper_parameter_tuning_jobs(StatusEquals="InProgress", NameContains=config.resource_prefix).get(
        "HyperParameterTuningJobSummaries", []
    ):
        sm.stop_hyper_parameter_tuning_job(HyperParameterTuningJobName=job["HyperParameterTuningJobName"])
        LOGGER.info("Stopped HPO Job %s", job["HyperParameterTuningJobName"])
    for job in sm.list_auto_ml_jobs(
        StatusEquals="InProgress",
        NameContains=config.resource_prefix[:11].rstrip("-"),
    ).get("AutoMLJobSummaries", []):
        sm.stop_auto_ml_job(AutoMLJobName=job["AutoMLJobName"])
        LOGGER.info("Stopped Autopilot Job %s", job["AutoMLJobName"])


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    if config.stop_active_jobs_on_cleanup:
        stop_active_jobs(config)
    if config.delete_pipeline_on_cleanup:
        delete_pipeline(config)
    if config.delete_model_registry_on_cleanup:
        delete_model_registry(config)
    if config.delete_experiments_on_cleanup:
        delete_experiments(config)
    if config.delete_feature_group_on_cleanup:
        delete_feature_group(config)
    if config.delete_s3_objects_on_cleanup:
        delete_s3_objects(config)
    else:
        LOGGER.warning(
            "DELETE_S3_OBJECTS_ON_CLEANUP=false. src.destroy_infra will still empty the stack-owned lab bucket "
            "before deleting CloudFormation; standalone cleanup_resources will not delete S3 objects."
        )


if __name__ == "__main__":
    main()
