"""Centralized AWS sessions and clients for the MLOps lab."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any

from .config import ConfigError, LabConfig, load_config


class AwsClientError(RuntimeError):
    """Raised when boto3 cannot create a session or client."""


@dataclass(frozen=True)
class AwsClients:
    session: Any
    sagemaker: Any
    sagemaker_runtime: Any
    s3: Any
    cloudwatch: Any
    events: Any
    sns: Any
    stepfunctions: Any
    lambda_client: Any
    iam: Any
    logs: Any


def create_session(config: LabConfig | None = None) -> Any:
    config = config or load_config(validate=False)
    if not config.aws_region:
        raise ConfigError("AWS_REGION is required to create a boto3 session.")

    try:
        import boto3
        from botocore.exceptions import ProfileNotFound
    except ImportError as exc:
        raise AwsClientError("boto3 is required. Run: pip install -r requirements.txt") from exc

    try:
        kwargs: dict[str, str] = {"region_name": config.aws_region}
        if config.aws_profile:
            kwargs["profile_name"] = config.aws_profile
        return boto3.Session(**kwargs)
    except ProfileNotFound as exc:
        raise AwsClientError(
            f"AWS profile '{config.aws_profile}' was not found. Check AWS_PROFILE or run aws configure."
        ) from exc


def create_clients(config: LabConfig | None = None) -> AwsClients:
    config = config or load_config(validate=False)
    session = create_session(config)

    return AwsClients(
        session=session,
        sagemaker=session.client("sagemaker"),
        sagemaker_runtime=session.client("sagemaker-runtime"),
        s3=session.client("s3"),
        cloudwatch=session.client("cloudwatch"),
        events=session.client("events"),
        sns=session.client("sns"),
        stepfunctions=session.client("stepfunctions"),
        lambda_client=session.client("lambda"),
        iam=session.client("iam"),
        logs=session.client("logs"),
    )


def client(service_name: str, config: LabConfig | None = None) -> Any:
    session = create_session(config)
    return session.client(service_name)


def _print_readiness(config: LabConfig, session_status: str, account_id: str = "") -> None:
    print("AWS setup readiness")
    print("===================")
    print(f"LAB_MODE: {config.lab_mode}")
    print(f"AWS_PROFILE: {config.aws_profile or '(default environment credentials)'}")
    print(f"AWS_REGION: {config.aws_region}")
    print(f"AWS_SESSION: {session_status}")
    if account_id:
        print(f"AWS_ACCOUNT_ID: {account_id}")
    print(f"S3_BUCKET_NAME: {config.s3_bucket_name or 'PENDING - run make deploy-infra or set S3_BUCKET_NAME'}")
    print(
        "SAGEMAKER_EXECUTION_ROLE_ARN: "
        f"{config.sagemaker_execution_role_arn or 'PENDING - run make deploy-infra or set SAGEMAKER_EXECUTION_ROLE_ARN'}"
    )
    print(
        "LAMBDA_EXECUTION_ROLE_ARN: "
        f"{config.lambda_execution_role_arn or 'PENDING - run make deploy-infra or set LAMBDA_EXECUTION_ROLE_ARN'}"
    )
    print(
        "STEPFUNCTIONS_ROLE_ARN: "
        f"{config.stepfunctions_role_arn or 'PENDING - run make deploy-infra or set STEPFUNCTIONS_ROLE_ARN'}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Check AWS client readiness for the MLOps lab.")
    parser.add_argument("--strict", action="store_true", help="Exit with an error if the AWS session cannot be validated.")
    args = parser.parse_args()

    config = load_config(validate=False)
    try:
        session = create_session(config)
        identity = session.client("sts").get_caller_identity()
    except Exception as exc:
        message = (
            "PENDING - could not validate AWS session. "
            "Check AWS_PROFILE, AWS_REGION, SSO/login, or environment credentials. "
            f"Detail: {exc}"
        )
        _print_readiness(config, message)
        if args.strict:
            raise AwsClientError(message) from exc
        return

    _print_readiness(config, "OK", account_id=identity.get("Account", ""))


if __name__ == "__main__":
    try:
        main()
    except (AwsClientError, ConfigError) as exc:
        raise SystemExit(str(exc))
