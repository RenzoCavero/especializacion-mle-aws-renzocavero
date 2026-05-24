from __future__ import annotations

import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.config import AppConfig


LOGGER = logging.getLogger(__name__)


def boto3_session(config: AppConfig) -> boto3.Session:
    if config.aws_profile:
        return boto3.Session(profile_name=config.aws_profile, region_name=config.aws_region)
    return boto3.Session(region_name=config.aws_region)


def client(config: AppConfig, service_name: str) -> Any:
    return boto3_session(config).client(service_name, region_name=config.aws_region)


def resource(config: AppConfig, service_name: str) -> Any:
    return boto3_session(config).resource(service_name, region_name=config.aws_region)


def sagemaker_session(config: AppConfig):
    import sagemaker

    return sagemaker.Session(
        boto_session=boto3_session(config),
        default_bucket=config.s3_bucket_name or None,
    )


def pipeline_session(config: AppConfig):
    from sagemaker.workflow.pipeline_context import PipelineSession

    return PipelineSession(
        boto_session=boto3_session(config),
        default_bucket=config.s3_bucket_name or None,
    )


def sklearn_image_uri(config: AppConfig) -> str:
    import sagemaker

    return sagemaker.image_uris.retrieve(
        framework="sklearn",
        region=config.aws_region,
        version="1.2-1",
        py_version="py3",
    )


def parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Expected S3 URI, got {uri}")
    without_scheme = uri[5:]
    bucket, _, key = without_scheme.partition("/")
    return bucket, key


def put_json_s3(config: AppConfig, data: dict[str, Any], s3_uri: str) -> None:
    import json

    bucket, key = parse_s3_uri(s3_uri)
    client(config, "s3").put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data, indent=2, sort_keys=True).encode("utf-8"),
        ContentType="application/json",
    )


def put_text_s3(config: AppConfig, text: str, s3_uri: str, content_type: str = "text/plain") -> None:
    bucket, key = parse_s3_uri(s3_uri)
    client(config, "s3").put_object(
        Bucket=bucket,
        Key=key,
        Body=text.encode("utf-8"),
        ContentType=content_type,
    )


def upload_file(config: AppConfig, local_path: str, s3_uri: str) -> None:
    bucket, key = parse_s3_uri(s3_uri)
    LOGGER.info("Uploading %s to %s", local_path, s3_uri)
    client(config, "s3").upload_file(local_path, bucket, key)


def download_file(config: AppConfig, s3_uri: str, local_path: str) -> None:
    bucket, key = parse_s3_uri(s3_uri)
    LOGGER.info("Downloading %s to %s", s3_uri, local_path)
    client(config, "s3").download_file(bucket, key, local_path)


def s3_key_exists(config: AppConfig, s3_uri: str) -> bool:
    bucket, key = parse_s3_uri(s3_uri)
    try:
        client(config, "s3").head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def copy_s3_object(config: AppConfig, source_uri: str, destination_uri: str) -> None:
    source_bucket, source_key = parse_s3_uri(source_uri)
    destination_bucket, destination_key = parse_s3_uri(destination_uri)
    client(config, "s3").copy_object(
        Bucket=destination_bucket,
        Key=destination_key,
        CopySource={"Bucket": source_bucket, "Key": source_key},
    )


def list_s3_keys(config: AppConfig, prefix_uri: str, max_keys: int = 20) -> list[str]:
    bucket, prefix = parse_s3_uri(prefix_uri)
    response = client(config, "s3").list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=max_keys)
    return [item["Key"] for item in response.get("Contents", [])]
