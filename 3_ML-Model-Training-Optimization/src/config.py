from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any

from src.instance_types import parse_instance_type_list, unique_instance_types


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
GENERATED_ENV_FILE = PROJECT_ROOT / ".env.cloud"
STATE_FILE = PROJECT_ROOT / "artifacts" / "local_outputs" / "run_state.json"


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
    """Load .env first and generated CloudFormation outputs second."""
    _load_env_file(ENV_FILE)
    _load_env_file(GENERATED_ENV_FILE)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def env_list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


def s3_join(bucket: str, *parts: str) -> str:
    clean = [part.strip("/") for part in parts if part and part.strip("/")]
    suffix = "/".join(clean)
    return f"s3://{bucket}/{suffix}" if suffix else f"s3://{bucket}"


def sdk_local_path(*parts: str) -> str:
    """Return a project-relative POSIX path for SageMaker SDK local uploads."""
    return PROJECT_ROOT.joinpath(*parts).relative_to(PROJECT_ROOT).as_posix()


@dataclass(frozen=True)
class AppConfig:
    aws_profile: str | None
    aws_region: str
    project_name: str
    environment: str
    resource_prefix: str
    stack_name: str
    s3_bucket_name: str
    sagemaker_execution_role_arn: str
    feature_group_name: str
    model_package_group_name: str
    enable_online_store: bool
    enable_offline_store: bool
    processing_instance_type: str
    training_instance_type: str
    processing_instance_type_fallbacks: tuple[str, ...]
    training_instance_type_fallbacks: tuple[str, ...]
    processing_instance_count: int
    training_instance_count: int
    hpo_max_jobs: int
    hpo_max_parallel_jobs: int
    wait_for_jobs: bool
    kms_key_arn: str | None
    delete_feature_group_on_cleanup: bool
    delete_s3_objects_on_cleanup: bool
    stop_active_jobs_on_cleanup: bool
    delete_model_registry_on_cleanup: bool
    delete_pipeline_on_cleanup: bool
    delete_experiments_on_cleanup: bool
    feature_data_source: str
    allow_feature_snapshot_fallback: bool
    offline_store_max_wait_seconds: int
    offline_store_poll_seconds: int
    processing_ingest_feature_store: bool
    autopilot_max_candidates: int
    autopilot_max_runtime_seconds: int
    autopilot_mode: str
    autopilot_algorithms: tuple[str, ...]

    @property
    def raw_data_local_path(self) -> Path:
        return PROJECT_ROOT / "data" / "local_cache" / "churn_raw.csv"

    @property
    def sample_data_local_path(self) -> Path:
        return PROJECT_ROOT / "data" / "sample" / "churn_sample.csv"

    @property
    def cleaned_data_local_path(self) -> Path:
        return PROJECT_ROOT / "data" / "local_cache" / "churn_cleaned.csv"

    @property
    def curated_features_local_path(self) -> Path:
        return PROJECT_ROOT / "data" / "local_cache" / "churn_features_curated.csv"

    @property
    def feature_lineage_local_path(self) -> Path:
        return PROJECT_ROOT / "artifacts" / "local_outputs" / "feature_lineage.json"

    @property
    def local_outputs_dir(self) -> Path:
        return PROJECT_ROOT / "artifacts" / "local_outputs"

    @property
    def offline_store_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "feature-store-offline") + "/"

    @property
    def raw_data_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "raw", "churn_raw.csv")

    @property
    def feature_snapshot_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "processing", "input", "churn_features.csv")

    @property
    def cleaned_data_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "cleaned", "churn_cleaned.csv")

    @property
    def curated_features_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "curated", "churn_features.csv")

    @property
    def feature_lineage_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "lineage", "feature_lineage.json")

    @property
    def athena_query_results_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "athena", "query-results") + "/"

    @property
    def train_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "input", "train")

    @property
    def validation_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "input", "validation")

    @property
    def test_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "input", "test")

    @property
    def baseline_output_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "output", "baseline")

    @property
    def hpo_output_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "output", "hpo")

    @property
    def best_model_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "output", "best_model", "model.tar.gz")

    @property
    def metrics_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "metrics")

    @property
    def reports_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "reports")

    @property
    def metadata_s3_uri(self) -> str:
        return s3_join(self.s3_bucket_name, "model_registry_metadata")

    @property
    def experiment_name(self) -> str:
        return f"{self.resource_prefix}-experiment"

    @property
    def pipeline_name(self) -> str:
        return f"{self.resource_prefix}-pipeline"

    @property
    def hpo_pipeline_name(self) -> str:
        return f"{self.resource_prefix}-hpo-pipeline"

    @property
    def processing_instance_candidates(self) -> tuple[str, ...]:
        return unique_instance_types(self.processing_instance_type, self.processing_instance_type_fallbacks)

    @property
    def training_instance_candidates(self) -> tuple[str, ...]:
        return unique_instance_types(self.training_instance_type, self.training_instance_type_fallbacks)

    def require_aws_fields(self) -> None:
        missing = []
        if not self.s3_bucket_name:
            missing.append("S3_BUCKET_NAME")
        if not self.sagemaker_execution_role_arn:
            missing.append("SAGEMAKER_EXECUTION_ROLE_ARN")
        if missing:
            names = ", ".join(missing)
            raise ValueError(
                f"Missing required AWS configuration: {names}. "
                "Run make deploy-infra or fill .env/.env.cloud."
            )

    def as_safe_dict(self) -> dict[str, Any]:
        return {
            "aws_profile": self.aws_profile,
            "aws_region": self.aws_region,
            "project_name": self.project_name,
            "environment": self.environment,
            "resource_prefix": self.resource_prefix,
            "stack_name": self.stack_name,
            "s3_bucket_name": self.s3_bucket_name,
            "feature_group_name": self.feature_group_name,
            "model_package_group_name": self.model_package_group_name,
            "pipeline_name": self.pipeline_name,
            "hpo_pipeline_name": self.hpo_pipeline_name,
            "enable_online_store": self.enable_online_store,
            "enable_offline_store": self.enable_offline_store,
            "processing_instance_type": self.processing_instance_type,
            "training_instance_type": self.training_instance_type,
            "processing_instance_type_fallbacks": list(self.processing_instance_type_fallbacks),
            "training_instance_type_fallbacks": list(self.training_instance_type_fallbacks),
            "hpo_max_jobs": self.hpo_max_jobs,
            "hpo_max_parallel_jobs": self.hpo_max_parallel_jobs,
            "feature_data_source": self.feature_data_source,
            "allow_feature_snapshot_fallback": self.allow_feature_snapshot_fallback,
            "offline_store_max_wait_seconds": self.offline_store_max_wait_seconds,
            "offline_store_poll_seconds": self.offline_store_poll_seconds,
            "processing_ingest_feature_store": self.processing_ingest_feature_store,
            "autopilot_max_candidates": self.autopilot_max_candidates,
            "autopilot_max_runtime_seconds": self.autopilot_max_runtime_seconds,
            "autopilot_mode": self.autopilot_mode,
            "autopilot_algorithms": list(self.autopilot_algorithms),
            "wait_for_jobs": self.wait_for_jobs,
            "kms_key_arn_configured": bool(self.kms_key_arn),
        }


def get_config() -> AppConfig:
    load_env()
    return AppConfig(
        aws_profile=os.getenv("AWS_PROFILE") or None,
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        project_name=os.getenv("PROJECT_NAME", "ml-model-training-optimization"),
        environment=os.getenv("ENVIRONMENT", "lab"),
        resource_prefix=os.getenv("RESOURCE_PREFIX", "ml-training-opt-lab"),
        stack_name=os.getenv("STACK_NAME", "ml-training-opt-lab"),
        s3_bucket_name=os.getenv("S3_BUCKET_NAME", ""),
        sagemaker_execution_role_arn=os.getenv("SAGEMAKER_EXECUTION_ROLE_ARN", ""),
        feature_group_name=os.getenv("FEATURE_GROUP_NAME", "churn-customer-features"),
        model_package_group_name=os.getenv("MODEL_PACKAGE_GROUP_NAME", "churn-model-package-group"),
        enable_online_store=env_bool("ENABLE_ONLINE_STORE", True),
        enable_offline_store=env_bool("ENABLE_OFFLINE_STORE", True),
        processing_instance_type=os.getenv("PROCESSING_INSTANCE_TYPE", "ml.t3.medium"),
        training_instance_type=os.getenv("TRAINING_INSTANCE_TYPE", "ml.t3.medium"),
        processing_instance_type_fallbacks=parse_instance_type_list(
            os.getenv("PROCESSING_INSTANCE_TYPE_FALLBACKS", "ml.t3.medium,ml.t3.large,ml.m5.large,ml.m5.xlarge")
        ),
        training_instance_type_fallbacks=parse_instance_type_list(
            os.getenv("TRAINING_INSTANCE_TYPE_FALLBACKS", "ml.t3.medium,ml.t3.large,ml.m5.large,ml.m5.xlarge")
        ),
        processing_instance_count=env_int("PROCESSING_INSTANCE_COUNT", 1),
        training_instance_count=env_int("TRAINING_INSTANCE_COUNT", 1),
        hpo_max_jobs=env_int("HPO_MAX_JOBS", 4),
        hpo_max_parallel_jobs=env_int("HPO_MAX_PARALLEL_JOBS", 1),
        wait_for_jobs=env_bool("WAIT_FOR_JOBS", True),
        kms_key_arn=os.getenv("KMS_KEY_ARN") or None,
        delete_feature_group_on_cleanup=env_bool("DELETE_FEATURE_GROUP_ON_CLEANUP", True),
        delete_s3_objects_on_cleanup=env_bool("DELETE_S3_OBJECTS_ON_CLEANUP", False),
        stop_active_jobs_on_cleanup=env_bool("STOP_ACTIVE_JOBS_ON_CLEANUP", False),
        delete_model_registry_on_cleanup=env_bool("DELETE_MODEL_REGISTRY_ON_CLEANUP", True),
        delete_pipeline_on_cleanup=env_bool("DELETE_PIPELINE_ON_CLEANUP", True),
        delete_experiments_on_cleanup=env_bool("DELETE_EXPERIMENTS_ON_CLEANUP", True),
        feature_data_source=os.getenv("FEATURE_DATA_SOURCE", "offline_store").strip().lower(),
        allow_feature_snapshot_fallback=env_bool("ALLOW_FEATURE_SNAPSHOT_FALLBACK", True),
        offline_store_max_wait_seconds=env_int("OFFLINE_STORE_MAX_WAIT_SECONDS", 900),
        offline_store_poll_seconds=env_int("OFFLINE_STORE_POLL_SECONDS", 60),
        processing_ingest_feature_store=env_bool("PROCESSING_INGEST_FEATURE_STORE", True),
        autopilot_max_candidates=env_int("AUTOPILOT_MAX_CANDIDATES", 2),
        autopilot_max_runtime_seconds=env_int("AUTOPILOT_MAX_RUNTIME_SECONDS", 900),
        autopilot_mode=os.getenv("AUTOPILOT_MODE", "ENSEMBLING").strip().upper(),
        autopilot_algorithms=env_list("AUTOPILOT_ALGORITHMS", ("linear-learner", "xgboost")),
    )
