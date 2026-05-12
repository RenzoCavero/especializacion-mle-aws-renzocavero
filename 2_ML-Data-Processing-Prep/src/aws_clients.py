"""AWS client helpers.

All scripts use profiles or IAM roles from the execution environment. This module
never reads or stores access keys.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.config import Settings, get_settings


def _boto3() -> Any:
    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required for AWS operations. Install dependencies with "
            "`pip install -r requirements.txt`."
        ) from exc
    return boto3


def session(settings: Optional[Settings] = None) -> Any:
    cfg = settings or get_settings()
    boto3 = _boto3()
    kwargs: Dict[str, str] = {"region_name": cfg.aws_region}
    if cfg.aws_profile:
        kwargs["profile_name"] = cfg.aws_profile
    return boto3.Session(**kwargs)


def client(service_name: str, settings: Optional[Settings] = None) -> Any:
    return session(settings).client(service_name)


def resource(service_name: str, settings: Optional[Settings] = None) -> Any:
    return session(settings).resource(service_name)


def get_stack_outputs(stack_name: Optional[str] = None, settings: Optional[Settings] = None) -> Dict[str, str]:
    cfg = settings or get_settings()
    cf = client("cloudformation", cfg)
    name = stack_name or cfg.stack_name
    response = cf.describe_stacks(StackName=name)
    outputs = response["Stacks"][0].get("Outputs", [])
    return {item["OutputKey"]: item["OutputValue"] for item in outputs}


def get_bucket_name(settings: Optional[Settings] = None) -> str:
    cfg = settings or get_settings()
    if cfg.s3_bucket_name:
        return cfg.s3_bucket_name
    outputs = get_stack_outputs(cfg.stack_name, cfg)
    bucket = outputs.get("BucketName")
    if not bucket:
        raise RuntimeError("BucketName output not found. Deploy infrastructure first.")
    return bucket


def get_glue_job_name(settings: Optional[Settings] = None) -> str:
    cfg = settings or get_settings()
    outputs = get_stack_outputs(cfg.stack_name, cfg)
    return outputs.get("GlueJobName", cfg.glue_job_name)


def get_glue_crawler_name(settings: Optional[Settings] = None) -> str:
    cfg = settings or get_settings()
    outputs = get_stack_outputs(cfg.stack_name, cfg)
    return outputs.get("GlueCrawlerName", cfg.glue_crawler_name)


def get_glue_data_quality_ruleset_name(settings: Optional[Settings] = None) -> str:
    cfg = settings or get_settings()
    return cfg.glue_data_quality_ruleset_name


def get_glue_database_name(settings: Optional[Settings] = None) -> str:
    cfg = settings or get_settings()
    outputs = get_stack_outputs(cfg.stack_name, cfg)
    return outputs.get("GlueDatabaseName", cfg.glue_database_name)


def get_processing_role_arn(settings: Optional[Settings] = None) -> str:
    cfg = settings or get_settings()
    if cfg.glue_role_arn:
        return cfg.glue_role_arn
    outputs = get_stack_outputs(cfg.stack_name, cfg)
    role_arn = outputs.get("ProcessingRoleArn")
    if not role_arn:
        raise RuntimeError("ProcessingRoleArn output not found. Deploy infrastructure first.")
    return role_arn
