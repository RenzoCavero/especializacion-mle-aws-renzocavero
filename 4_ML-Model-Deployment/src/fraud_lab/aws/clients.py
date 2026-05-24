from __future__ import annotations

from typing import Any

from src.aws_clients import boto3_session

from fraud_lab.aws.config import FraudAwsConfig, load_fraud_aws_config


class FraudAwsClients:
    """Clientes boto3 usados por la arquitectura cloud de fraude."""

    def __init__(self, config: FraudAwsConfig | None = None) -> None:
        self.config = config or load_fraud_aws_config()
        self.session = boto3_session(self.config.aws_profile, self.config.aws_region)

    def client(self, service_name: str) -> Any:
        return self.session.client(service_name)

    def resource(self, service_name: str) -> Any:
        return self.session.resource(service_name)

    @property
    def s3(self) -> Any:
        return self.client("s3")

    @property
    def dynamodb_resource(self) -> Any:
        return self.resource("dynamodb")

    @property
    def sqs(self) -> Any:
        return self.client("sqs")

    @property
    def sagemaker(self) -> Any:
        return self.client("sagemaker")

    @property
    def featurestore_runtime(self) -> Any:
        return self.client("sagemaker-featurestore-runtime")

    @property
    def sagemaker_runtime(self) -> Any:
        return self.client("sagemaker-runtime")


def clients(config: FraudAwsConfig | None = None) -> FraudAwsClients:
    return FraudAwsClients(config)

