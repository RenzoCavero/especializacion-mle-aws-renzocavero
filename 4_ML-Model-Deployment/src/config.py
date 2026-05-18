from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args: object, **kwargs: object) -> bool:
        return False

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT_DIR / ".env"
GENERATED_ENV_FILE = ROOT_DIR / ".env.cloud"
LOCAL_OUTPUTS_DIR = ROOT_DIR / "artifacts" / "local_outputs"
LOCAL_CACHE_DIR = ROOT_DIR / "data" / "local_cache"
SAMPLE_DATA_DIR = ROOT_DIR / "data" / "sample"
VALID_LAB_MODES = {"standalone", "integrated"}


class ConfigError(ValueError):
    """Raised when the lab configuration is incomplete or unsafe."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def ensure_local_dirs() -> None:
    for path in (LOCAL_OUTPUTS_DIR, LOCAL_CACHE_DIR, SAMPLE_DATA_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value == "":
            continue
        if os.environ.get(key, "") == "":
            os.environ[key] = value


def load_env() -> None:
    """Load .env first, then generated CloudFormation outputs."""
    _load_env_file(ENV_FILE)
    _load_env_file(GENERATED_ENV_FILE)


def normalize_lab_mode(value: str | None) -> str:
    mode = (value or "standalone").strip().lower().replace("_mode", "")
    if mode not in VALID_LAB_MODES:
        raise ConfigError(
            "LAB_MODE debe ser 'standalone' o 'integrated'. "
            f"Valor recibido: {value!r}."
        )
    return mode


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} debe ser un entero. Valor recibido: {value!r}.") from exc


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigError(f"{name} debe ser numerico. Valor recibido: {value!r}.") from exc


def clean_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def safe_name(value: str, max_len: int = 63) -> str:
    normalized = re.sub(r"[^A-Za-z0-9-]+", "-", value.strip())
    normalized = re.sub(r"-+", "-", normalized).strip("-").lower()
    return normalized[:max_len].strip("-") or "ml-deploy-lab"


def parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ConfigError(f"URI S3 invalida: {uri!r}. Debe iniciar con s3://.")
    without_scheme = uri[5:]
    bucket, _, key = without_scheme.partition("/")
    if not bucket:
        raise ConfigError(f"URI S3 invalida sin bucket: {uri!r}.")
    return bucket, key


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        if default is not None:
            return default
        raise ConfigError(f"No existe el archivo requerido: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(slots=True)
class FeatureContract:
    feature_group_name: str = ""
    record_identifier_name: str = "customer_id"
    event_time_feature_name: str = "event_time"
    training_features: list[str] = field(default_factory=list)
    inference_features: list[str] = field(default_factory=list)
    target_column: str = "target"
    batch_identifier_column: str = "customer_id"
    realtime_lookup_key: str = "customer_id"
    offline_store_s3_uri: str = ""
    model_package_group_name: str = ""
    model_artifact_s3_uri: str = ""

    @classmethod
    def standalone(cls) -> "FeatureContract":
        features = [
            "age",
            "income",
            "account_tenure_months",
            "monthly_spend",
            "support_tickets_90d",
        ]
        return cls(
            training_features=features,
            inference_features=features,
            target_column="churned",
            batch_identifier_column="customer_id",
            realtime_lookup_key="customer_id",
        )

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "FeatureContract":
        base = cls.standalone()
        values = asdict(base)
        values.update({k: v for k, v in raw.items() if k in values and v is not None})
        for key in ("training_features", "inference_features"):
            value = values.get(key) or []
            if isinstance(value, str):
                value = [item.strip() for item in value.split(",") if item.strip()]
            values[key] = list(value)
        contract = cls(**values)
        contract.validate()
        return contract

    def validate(self) -> None:
        if not self.inference_features:
            raise ConfigError("El feature contract debe definir inference_features.")
        if self.target_column in self.inference_features:
            raise ConfigError("target_column no puede estar en inference_features.")
        if not self.batch_identifier_column:
            raise ConfigError("El feature contract debe definir batch_identifier_column.")
        if not self.realtime_lookup_key:
            raise ConfigError("El feature contract debe definir realtime_lookup_key.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LabConfig:
    lab_mode: str
    aws_profile: str
    aws_region: str
    project_name: str
    environment: str
    resource_prefix: str
    stack_name: str
    s3_bucket_name: str
    s3_prefix: str
    sagemaker_execution_role_arn: str
    model_package_group_name: str
    model_package_arn: str
    model_artifact_s3_uri: str
    feature_group_name: str
    offline_store_s3_uri: str
    feature_contract_s3_uri: str
    create_standalone_model: bool
    create_standalone_feature_group: bool
    endpoint_name: str
    endpoint_config_name: str
    model_name: str
    batch_job_prefix: str
    instance_type: str
    initial_instance_count: int
    batch_instance_type: str
    batch_instance_count: int
    split_type: str
    batch_strategy: str
    max_payload_mb: int
    max_concurrent_transforms: int
    enable_data_capture: bool
    enable_autoscaling: bool
    autoscaling_min_capacity: int
    autoscaling_max_capacity: int
    autoscaling_target_invocations_per_instance: float
    wait_for_batch: bool
    wait_for_endpoint: bool
    realtime_record_id: str
    inference_image_uri: str
    kms_key_id: str
    delete_lab_s3: bool

    @classmethod
    def from_env(cls, require_aws: bool = False) -> "LabConfig":
        load_env()
        ensure_local_dirs()

        lab_mode = normalize_lab_mode(clean_env("LAB_MODE", "standalone"))
        project_name = clean_env("PROJECT_NAME", "ml-model-deployment")
        environment = clean_env("ENVIRONMENT", "lab")
        resource_prefix = safe_name(clean_env("RESOURCE_PREFIX", "ml-deploy-lab"))
        stack_name = safe_name(clean_env("STACK_NAME", resource_prefix))
        s3_prefix = clean_env("S3_PREFIX", f"{resource_prefix}/{environment}")

        create_standalone_feature_group = env_bool("CREATE_STANDALONE_FEATURE_GROUP", True)
        if lab_mode == "standalone":
            create_standalone_feature_group = True
        feature_group_name = clean_env("FEATURE_GROUP_NAME")
        if not feature_group_name and create_standalone_feature_group:
            feature_group_name = safe_name(f"{resource_prefix}-features")

        config = cls(
            lab_mode=lab_mode,
            aws_profile=clean_env("AWS_PROFILE"),
            aws_region=clean_env("AWS_REGION", "us-east-1"),
            project_name=project_name,
            environment=environment,
            resource_prefix=resource_prefix,
            stack_name=stack_name,
            s3_bucket_name=clean_env("S3_BUCKET_NAME"),
            s3_prefix=s3_prefix.strip("/"),
            sagemaker_execution_role_arn=clean_env("SAGEMAKER_EXECUTION_ROLE_ARN"),
            model_package_group_name=clean_env("MODEL_PACKAGE_GROUP_NAME"),
            model_package_arn=clean_env("MODEL_PACKAGE_ARN"),
            model_artifact_s3_uri=clean_env("MODEL_ARTIFACT_S3_URI"),
            feature_group_name=feature_group_name,
            offline_store_s3_uri=clean_env("OFFLINE_STORE_S3_URI"),
            feature_contract_s3_uri=clean_env("FEATURE_CONTRACT_S3_URI"),
            create_standalone_model=env_bool("CREATE_STANDALONE_MODEL", True),
            create_standalone_feature_group=create_standalone_feature_group,
            endpoint_name=safe_name(clean_env("ENDPOINT_NAME", "ml-deploy-realtime-endpoint")),
            endpoint_config_name=safe_name(clean_env("ENDPOINT_CONFIG_NAME", "ml-deploy-realtime-config")),
            model_name=safe_name(clean_env("MODEL_NAME", "ml-deploy-model")),
            batch_job_prefix=safe_name(clean_env("BATCH_JOB_PREFIX", "ml-deploy-batch")),
            instance_type=clean_env("INSTANCE_TYPE", "ml.m5.large"),
            initial_instance_count=env_int("INITIAL_INSTANCE_COUNT", 1),
            batch_instance_type=clean_env("BATCH_INSTANCE_TYPE", "ml.m5.large"),
            batch_instance_count=env_int("BATCH_INSTANCE_COUNT", 1),
            split_type=clean_env("BATCH_SPLIT_TYPE", "Line"),
            batch_strategy=clean_env("BATCH_STRATEGY", "SingleRecord"),
            max_payload_mb=env_int("MAX_PAYLOAD_IN_MB", 6),
            max_concurrent_transforms=env_int("MAX_CONCURRENT_TRANSFORMS", 1),
            enable_data_capture=env_bool("ENABLE_DATA_CAPTURE", True),
            enable_autoscaling=env_bool("ENABLE_AUTOSCALING", True),
            autoscaling_min_capacity=env_int("AUTOSCALING_MIN_CAPACITY", 1),
            autoscaling_max_capacity=env_int("AUTOSCALING_MAX_CAPACITY", 2),
            autoscaling_target_invocations_per_instance=env_float(
                "AUTOSCALING_TARGET_INVOCATIONS_PER_INSTANCE", 50.0
            ),
            wait_for_batch=env_bool("WAIT_FOR_BATCH", True),
            wait_for_endpoint=env_bool("WAIT_FOR_ENDPOINT", True),
            realtime_record_id=clean_env("REALTIME_RECORD_ID"),
            inference_image_uri=clean_env("INFERENCE_IMAGE_URI"),
            kms_key_id=clean_env("KMS_KEY_ID"),
            delete_lab_s3=env_bool("DELETE_LAB_S3", False),
        )
        if require_aws:
            config.validate_for_aws()
        return config

    def validate_for_aws(self) -> None:
        missing = []
        if not self.aws_region:
            missing.append("AWS_REGION")
        if not self.s3_bucket_name:
            missing.append("S3_BUCKET_NAME")
        if not self.sagemaker_execution_role_arn:
            missing.append("SAGEMAKER_EXECUTION_ROLE_ARN")
        if missing:
            raise ConfigError(
                "Faltan variables requeridas para ejecutar en AWS: "
                + ", ".join(missing)
                + ". Completa .env o exporta las variables antes de ejecutar."
            )
        if self.lab_mode == "integrated" and not (
            self.model_package_arn
            or self.model_package_group_name
            or self.model_artifact_s3_uri
        ):
            raise ConfigError(
                "integrated_mode requiere MODEL_PACKAGE_ARN, "
                "MODEL_PACKAGE_GROUP_NAME o MODEL_ARTIFACT_S3_URI."
            )

    @property
    def tags(self) -> list[dict[str, str]]:
        return [
            {"Key": "Project", "Value": "MLModelDeployment"},
            {"Key": "Environment", "Value": self.environment.title()},
            {"Key": "Owner", "Value": "LabUser"},
            {"Key": "ManagedBy", "Value": "Lab04Code"},
            {"Key": "CostCenter", "Value": "Training"},
            {"Key": "AutoDelete", "Value": "true"},
        ]

    def s3_uri(self, *parts: str) -> str:
        if not self.s3_bucket_name:
            raise ConfigError("S3_BUCKET_NAME no esta definido.")
        key_parts = [self.s3_prefix.strip("/")]
        key_parts.extend(str(part).strip("/") for part in parts if str(part).strip("/"))
        return f"s3://{self.s3_bucket_name}/{'/'.join(key_parts)}"

    @property
    def model_artifact_output_s3_uri(self) -> str:
        return self.s3_uri("artifacts", "standalone", "model.tar.gz")

    @property
    def batch_input_s3_prefix(self) -> str:
        return self.s3_uri("batch", "input")

    @property
    def batch_output_s3_prefix(self) -> str:
        return self.s3_uri("batch", "output")

    @property
    def reports_s3_prefix(self) -> str:
        return self.s3_uri("reports")

    @property
    def data_capture_s3_uri(self) -> str:
        return self.s3_uri("data-capture", self.endpoint_name)

    def metadata_path(self, file_name: str) -> Path:
        return LOCAL_OUTPUTS_DIR / file_name

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(require_aws: bool = False) -> LabConfig:
    return LabConfig.from_env(require_aws=require_aws)


def load_feature_contract(config: LabConfig | None = None) -> FeatureContract:
    config = config or load_config(require_aws=False)
    local_contract = LOCAL_CACHE_DIR / "feature_contract.json"
    if local_contract.exists():
        return FeatureContract.from_mapping(read_json(local_contract))
    return FeatureContract.standalone()


def save_feature_contract(contract: FeatureContract) -> Path:
    path = LOCAL_CACHE_DIR / "feature_contract.json"
    write_json(path, contract.to_dict())
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida y muestra la configuracion del laboratorio 4.")
    parser.add_argument("--require-aws", action="store_true", help="Validar variables requeridas para AWS.")
    parser.add_argument(
        "--check-aws",
        action="store_true",
        help="Mostrar readiness AWS sin fallar; util para pasos de setup.",
    )
    args = parser.parse_args()
    try:
        config = load_config(require_aws=args.require_aws)
        if args.check_aws:
            required = {
                "AWS_REGION": config.aws_region,
                "S3_BUCKET_NAME": config.s3_bucket_name,
                "SAGEMAKER_EXECUTION_ROLE_ARN": config.sagemaker_execution_role_arn,
            }
            optional = {"AWS_PROFILE": config.aws_profile or "(usa credenciales/rol del entorno)"}
            print("AWS setup readiness")
            print("===================")
            print(f"LAB_MODE: {config.lab_mode}")
            print(f"FEATURE_GROUP_NAME: {config.feature_group_name or 'PENDIENTE'}")
            for name, value in optional.items():
                print(f"{name}: {value}")
            missing = []
            for name, value in required.items():
                status = value or "PENDIENTE"
                print(f"{name}: {status}")
                if not value:
                    missing.append(name)
            if not missing:
                print("\nEstado: OK. Variables minimas completas para ejecutar recursos AWS.")
                return
            print("\nEstado: pendiente.")
            print("Faltan variables requeridas: " + ", ".join(missing))
            print(
                "\nOpcion A - usar recursos existentes: edita .env y completa, por ejemplo:\n"
                "AWS_PROFILE=tu-profile\n"
                "AWS_REGION=us-east-1\n"
                "S3_BUCKET_NAME=tu-bucket-privado\n"
                "SAGEMAKER_EXECUTION_ROLE_ARN=arn:aws:iam::<account-id>:role/<role-name>\n"
            )
            print(
                "Opcion B - crear infraestructura base con CloudFormation:\n"
                "1. Exporta AWS_PROFILE y AWS_REGION si aplica.\n"
                "2. Ejecuta: make deploy-infra o scripts/deploy_infra.sh\n"
                "3. El comando genera .env.cloud automaticamente con BucketName "
                "y SageMakerExecutionRoleArn.\n"
            )
            print(
                "Nota: copiar .env.example a .env solo crea la plantilla; no rellena valores AWS."
            )
        else:
            printable = config.to_dict()
            print(json.dumps(printable, indent=2, sort_keys=True))
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
