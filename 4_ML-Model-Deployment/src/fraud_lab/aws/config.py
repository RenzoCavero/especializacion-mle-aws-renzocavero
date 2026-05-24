from __future__ import annotations

from dataclasses import dataclass

from src.config import ConfigError, LabConfig, clean_env, env_bool, env_int, load_config, safe_name


@dataclass(frozen=True)
class FraudAwsConfig:
    """Configuracion cloud para la arquitectura de fraude."""

    lab_config: LabConfig
    fraud_s3_prefix: str
    fraud_decision_table_name: str
    fraud_event_queue_url: str
    fraud_event_queue_name: str
    fraud_feature_group_prefix: str
    fraud_model_package_group_name: str
    fraud_model_package_arn: str
    fraud_model_artifact_s3_uri: str
    fraud_model_name: str
    fraud_endpoint_config_name: str
    fraud_use_sagemaker_endpoint: bool
    fraud_endpoint_name: str
    fraud_instance_type: str
    fraud_initial_instance_count: int
    fraud_enable_data_capture: bool
    fraud_batch_instance_type: str
    fraud_batch_instance_count: int
    fraud_require_batch_transform: bool

    @classmethod
    def from_env(
        cls,
        *,
        require_aws: bool = True,
        require_operational: bool = True,
    ) -> "FraudAwsConfig":
        lab_config = load_config(require_aws=require_aws)
        fraud_s3_prefix = clean_env(
            "FRAUD_S3_PREFIX",
            f"{lab_config.s3_prefix}/fraud",
        ).strip("/")
        fraud_decision_table_name = clean_env(
            "FRAUD_DECISION_TABLE_NAME",
            f"{lab_config.resource_prefix}-fraud-decisions-{lab_config.aws_region}",
        )
        fraud_event_queue_url = clean_env("FRAUD_EVENT_QUEUE_URL")
        fraud_event_queue_name = clean_env(
            "FRAUD_EVENT_QUEUE_NAME",
            f"{lab_config.resource_prefix}-fraud-events-{lab_config.aws_region}",
        )
        fraud_feature_group_prefix = safe_name(
            clean_env("FRAUD_FEATURE_GROUP_PREFIX", f"{lab_config.resource_prefix}-fraud"),
            max_len=32,
        )
        fraud_model_package_group_name = safe_name(
            clean_env("FRAUD_MODEL_PACKAGE_GROUP_NAME", f"{lab_config.resource_prefix}-fraud-models"),
            max_len=63,
        )
        fraud_model_package_arn = clean_env("FRAUD_MODEL_PACKAGE_ARN")
        fraud_model_artifact_s3_uri = clean_env("FRAUD_MODEL_ARTIFACT_S3_URI")
        fraud_model_name = safe_name(
            clean_env("FRAUD_MODEL_NAME", f"{lab_config.resource_prefix}-fraud-model"),
            max_len=63,
        )
        fraud_endpoint_config_name = safe_name(
            clean_env(
                "FRAUD_ENDPOINT_CONFIG_NAME",
                f"{lab_config.resource_prefix}-fraud-realtime-config",
            ),
            max_len=63,
        )
        fraud_use_sagemaker_endpoint = env_bool("FRAUD_USE_SAGEMAKER_ENDPOINT", False)
        raw_fraud_endpoint_name = clean_env("FRAUD_ENDPOINT_NAME")
        if not raw_fraud_endpoint_name or raw_fraud_endpoint_name == "ml-deploy-realtime-endpoint":
            raw_fraud_endpoint_name = f"{lab_config.resource_prefix}-fraud-realtime-endpoint"
        fraud_endpoint_name = safe_name(raw_fraud_endpoint_name, max_len=63)
        fraud_instance_type = clean_env("FRAUD_INSTANCE_TYPE", lab_config.instance_type)
        fraud_initial_instance_count = env_int(
            "FRAUD_INITIAL_INSTANCE_COUNT",
            lab_config.initial_instance_count,
        )
        fraud_enable_data_capture = env_bool(
            "FRAUD_ENABLE_DATA_CAPTURE",
            lab_config.enable_data_capture,
        )
        fraud_batch_instance_type = clean_env(
            "FRAUD_BATCH_INSTANCE_TYPE",
            "ml.c6i.large,ml.m6i.large,ml.m5.xlarge,ml.m5.large",
        )
        fraud_batch_instance_count = env_int(
            "FRAUD_BATCH_INSTANCE_COUNT",
            lab_config.batch_instance_count,
        )
        fraud_require_batch_transform = env_bool("FRAUD_REQUIRE_BATCH_TRANSFORM", False)

        config = cls(
            lab_config=lab_config,
            fraud_s3_prefix=fraud_s3_prefix,
            fraud_decision_table_name=fraud_decision_table_name,
            fraud_event_queue_url=fraud_event_queue_url,
            fraud_event_queue_name=fraud_event_queue_name,
            fraud_feature_group_prefix=fraud_feature_group_prefix,
            fraud_model_package_group_name=fraud_model_package_group_name,
            fraud_model_package_arn=fraud_model_package_arn,
            fraud_model_artifact_s3_uri=fraud_model_artifact_s3_uri,
            fraud_model_name=fraud_model_name,
            fraud_endpoint_config_name=fraud_endpoint_config_name,
            fraud_use_sagemaker_endpoint=fraud_use_sagemaker_endpoint,
            fraud_endpoint_name=fraud_endpoint_name,
            fraud_instance_type=fraud_instance_type,
            fraud_initial_instance_count=fraud_initial_instance_count,
            fraud_enable_data_capture=fraud_enable_data_capture,
            fraud_batch_instance_type=fraud_batch_instance_type,
            fraud_batch_instance_count=fraud_batch_instance_count,
            fraud_require_batch_transform=fraud_require_batch_transform,
        )
        if require_operational:
            config.validate_operational_resources()
        return config

    @property
    def aws_profile(self) -> str:
        return self.lab_config.aws_profile

    @property
    def aws_region(self) -> str:
        return self.lab_config.aws_region

    @property
    def s3_bucket_name(self) -> str:
        return self.lab_config.s3_bucket_name

    @property
    def sagemaker_execution_role_arn(self) -> str:
        return self.lab_config.sagemaker_execution_role_arn

    @property
    def tags(self) -> list[dict[str, str]]:
        return self.lab_config.tags

    @property
    def fraud_batch_instance_type_candidates(self) -> list[str]:
        return [
            instance_type.strip()
            for instance_type in self.fraud_batch_instance_type.split(",")
            if instance_type.strip()
        ]

    def validate_operational_resources(self) -> None:
        missing: list[str] = []
        if not self.fraud_decision_table_name:
            missing.append("FRAUD_DECISION_TABLE_NAME")
        if not self.fraud_event_queue_url:
            missing.append("FRAUD_EVENT_QUEUE_URL")
        if missing:
            raise ConfigError(
                "Faltan recursos AWS para el modo fraude cloud: "
                + ", ".join(missing)
                + ". Ejecuta make deploy-infra o scripts/deploy_infra.sh para generar .env.cloud."
            )

    def s3_key(self, *parts: str) -> str:
        key_parts = [self.fraud_s3_prefix]
        key_parts.extend(str(part).strip("/") for part in parts if str(part).strip("/"))
        return "/".join(key_parts)

    def s3_uri(self, *parts: str) -> str:
        return f"s3://{self.s3_bucket_name}/{self.s3_key(*parts)}"

    def physical_feature_group_name(self, logical_group: str) -> str:
        suffix = logical_group.replace("_", "-")
        return safe_name(f"{self.fraud_feature_group_prefix}-{suffix}", max_len=63)


def load_fraud_aws_config(
    *,
    require_aws: bool = True,
    require_operational: bool = True,
) -> FraudAwsConfig:
    return FraudAwsConfig.from_env(
        require_aws=require_aws,
        require_operational=require_operational,
    )
