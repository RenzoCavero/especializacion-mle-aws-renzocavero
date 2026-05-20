from __future__ import annotations

import importlib
from functools import lru_cache
from typing import Any

from .config import ConfigError, LabConfig, load_config


def _import_boto3() -> Any:
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError, ProfileNotFound
    except ImportError as exc:
        raise ConfigError(
            "boto3/botocore no estan instalados. Ejecuta: pip install -r requirements.txt"
        ) from exc
    return boto3, NoCredentialsError, ProfileNotFound


@lru_cache(maxsize=4)
def boto3_session(profile_name: str = "", region_name: str = "") -> Any:
    boto3, _, ProfileNotFound = _import_boto3()
    if not region_name:
        raise ConfigError("AWS_REGION no esta definido.")
    try:
        kwargs: dict[str, str] = {"region_name": region_name}
        if profile_name:
            kwargs["profile_name"] = profile_name
        return boto3.Session(**kwargs)
    except ProfileNotFound as exc:
        raise ConfigError(
            f"El AWS_PROFILE '{profile_name}' no existe. Revisa aws configure list-profiles."
        ) from exc


class AwsClients:
    def __init__(self, config: LabConfig | None = None) -> None:
        self.config = config or load_config(require_aws=True)
        self.session = boto3_session(self.config.aws_profile, self.config.aws_region)

    def client(self, service_name: str) -> Any:
        return self.session.client(service_name)

    @property
    def sagemaker(self) -> Any:
        return self.client("sagemaker")

    @property
    def sagemaker_runtime(self) -> Any:
        return self.client("sagemaker-runtime")

    @property
    def featurestore_runtime(self) -> Any:
        return self.client("sagemaker-featurestore-runtime")

    @property
    def s3(self) -> Any:
        return self.client("s3")

    @property
    def cloudwatch(self) -> Any:
        return self.client("cloudwatch")

    @property
    def application_autoscaling(self) -> Any:
        return self.client("application-autoscaling")

    @property
    def iam(self) -> Any:
        return self.client("iam")

    @property
    def cloudformation(self) -> Any:
        return self.client("cloudformation")


def clients(config: LabConfig | None = None) -> AwsClients:
    return AwsClients(config=config)


def client_error_code(exc: Exception) -> str:
    response = getattr(exc, "response", {}) or {}
    return response.get("Error", {}).get("Code", exc.__class__.__name__)


def _retrieve_sklearn_image_with_sdk(config: LabConfig) -> str | None:
    for module_name in ("sagemaker.image_uris", "sagemaker.core.image_uris"):
        try:
            image_uris = importlib.import_module(module_name)
            retrieve = getattr(image_uris, "retrieve", None)
            if retrieve is None:
                continue
            return retrieve(
                framework="sklearn",
                region=config.aws_region,
                version="1.2-1",
                py_version="py3",
                instance_type=config.instance_type,
                image_scope="inference",
            )
        except Exception:
            continue
    return None


def _fallback_sklearn_image_uri(config: LabConfig) -> str:
    framework_accounts = {
        "af-south-1": "626614931356",
        "ap-east-1": "871362719292",
        "ap-northeast-1": "354813040037",
        "ap-northeast-2": "366743142698",
        "ap-south-1": "720646828776",
        "ap-southeast-1": "121021644041",
        "ap-southeast-2": "783357654285",
        "ca-central-1": "341280168497",
        "eu-central-1": "492215442770",
        "eu-north-1": "662702820516",
        "eu-south-1": "692866216735",
        "eu-west-1": "141502667606",
        "eu-west-2": "764974769150",
        "eu-west-3": "659782779980",
        "me-south-1": "217643126080",
        "sa-east-1": "737474898029",
        "us-east-1": "683313688378",
        "us-east-2": "257758044811",
        "us-west-1": "746614075791",
        "us-west-2": "246618743249",
    }
    account_id = framework_accounts.get(config.aws_region)
    if not account_id:
        raise ConfigError(
            "No se pudo resolver la imagen de scikit-learn para SageMaker. "
            "Define INFERENCE_IMAGE_URI en .env con una imagen compatible para tu region."
        )
    return (
        f"{account_id}.dkr.ecr.{config.aws_region}.amazonaws.com/"
        "sagemaker-scikit-learn:1.2-1-cpu-py3"
    )


def get_sklearn_image_uri(config: LabConfig) -> str:
    if config.inference_image_uri:
        return config.inference_image_uri
    image_uri = _retrieve_sklearn_image_with_sdk(config)
    if image_uri:
        return image_uri
    return _fallback_sklearn_image_uri(config)
