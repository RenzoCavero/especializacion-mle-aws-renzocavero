"""Central configuration for the AWS MLOps laboratory.

The module intentionally does not create AWS clients. It only reads environment
variables, validates the lab mode, builds resource names and S3 URIs, and offers
small helpers for local metadata files.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


VALID_LAB_MODES = {"standalone", "integrated"}
ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT_DIR / ".env"
GENERATED_ENV_FILE = ROOT_DIR / ".env.cloud"
DEFAULT_ENDPOINT_INSTANCE_TYPE_CANDIDATES = "ml.c6i.large,ml.m6i.large,ml.m5.large,ml.m5.xlarge"
DEFAULT_PROCESSING_INSTANCE_TYPE_CANDIDATES = "ml.t3.medium,ml.t3.large,ml.m6i.large,ml.m5.xlarge,ml.m5.large,ml.c6i.xlarge,ml.c5.xlarge"
DEFAULT_MODEL_MONITOR_PROCESSING_INSTANCE_TYPE_CANDIDATES = "ml.m6i.large,ml.m5.xlarge,ml.c6i.xlarge,ml.c5.xlarge,ml.t3.large,ml.t3.medium"
DEFAULT_TRAINING_INSTANCE_TYPE_CANDIDATES = "ml.m6i.large,ml.m5.xlarge,ml.m5.large,ml.c6i.xlarge,ml.c5.xlarge"
DEFAULT_BATCH_TRANSFORM_INSTANCE_TYPE_CANDIDATES = "ml.c6i.large,ml.m6i.large,ml.m5.xlarge,ml.m5.large,ml.c6i.xlarge,ml.c5.xlarge"


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


def _load_plain_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value and not os.environ.get(key):
            os.environ[key] = value


def _load_dotenv() -> None:
    try:
        from dotenv import dotenv_values
    except ImportError:
        _load_plain_env(ENV_FILE)
        _load_plain_env(GENERATED_ENV_FILE)
        return

    for path in (ENV_FILE, GENERATED_ENV_FILE):
        if not path.exists():
            continue
        for key, value in dotenv_values(path).items():
            if value is None or value.strip() == "":
                continue
            if os.environ.get(key, "") == "":
                os.environ[key] = value.strip()


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _bool_env(name: str, default: bool = False) -> bool:
    value = _env(name, str(default)).lower()
    return value in {"1", "true", "yes", "y", "on"}


def _csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_s3_uri(uri: str) -> str:
    return uri.rstrip("/")


def safe_name(value: str, max_len: int = 63) -> str:
    normalized = re.sub(r"[^A-Za-z0-9-]+", "-", value.strip())
    normalized = re.sub(r"-+", "-", normalized).strip("-").lower()
    return normalized[:max_len].strip("-") or "mlops-lab"


@dataclass(frozen=True)
class LabConfig:
    lab_mode: str = "standalone"
    aws_profile: str = ""
    aws_region: str = ""
    project_name: str = "mlops-aws"
    environment: str = "lab"
    resource_prefix: str = "mlops-lab"
    s3_bucket_name: str = ""
    sagemaker_execution_role_arn: str = ""

    model_package_group_name: str = "mlops-model-package-group"
    model_package_arn: str = ""
    model_artifact_s3_uri: str = ""
    model_image_uri: str = ""
    model_monitor_image_uri: str = ""
    endpoint_name: str = "mlops-lab-endpoint"

    feature_group_name: str = ""
    feature_contract_s3_uri: str = ""
    data_capture_s3_uri_override: str = ""

    create_standalone_dataset: bool = True
    create_standalone_model: bool = True
    create_endpoint: bool = True
    enable_data_capture: bool = True
    capture_endpoint_output: bool = True
    enable_model_monitor: bool = True
    enable_cloudwatch_alarm: bool = True
    enable_eventbridge: bool = True
    enable_feedback_loop: bool = True
    enable_automatic_retraining: bool = False
    enable_rollback_execution: bool = False
    enable_baseline_update: bool = False
    auto_select_compute: bool = True

    instance_type: str = "ml.m5.large"
    training_instance_type: str = "ml.m5.large"
    processing_instance_type: str = "ml.m5.large"
    model_monitor_processing_instance_type: str = "ml.m6i.large"
    instance_type_candidates: str = DEFAULT_ENDPOINT_INSTANCE_TYPE_CANDIDATES
    training_instance_type_candidates: str = DEFAULT_TRAINING_INSTANCE_TYPE_CANDIDATES
    processing_instance_type_candidates: str = DEFAULT_PROCESSING_INSTANCE_TYPE_CANDIDATES
    model_monitor_processing_instance_type_candidates: str = DEFAULT_MODEL_MONITOR_PROCESSING_INSTANCE_TYPE_CANDIDATES
    batch_transform_instance_type_candidates: str = DEFAULT_BATCH_TRANSFORM_INSTANCE_TYPE_CANDIDATES

    pipeline_name: str = "mlops-build-pipeline"
    monitoring_schedule_name: str = "mlops-monitoring-schedule"
    alarm_name: str = "mlops-data-quality-alarm"
    model_quality_schedule_name: str = "mlops-model-quality-schedule"
    model_quality_job_definition_name: str = "mlops-model-quality-job-def"
    model_quality_alarm_name: str = "mlops-model-quality-alarm"
    custom_data_quality_alarm_name: str = "mlops-custom-data-quality-alarm"
    custom_batch_data_quality_alarm_name: str = "mlops-custom-batch-data-quality-alarm"
    custom_model_quality_alarm_name: str = "mlops-custom-model-quality-alarm"
    custom_model_quality_schedule_name: str = "mlops-custom-model-quality-schedule"
    custom_model_quality_trigger_lambda_name: str = "mlops-custom-model-quality-trigger"
    custom_data_quality_schedule_name: str = "mlops-custom-data-quality-schedule"
    custom_data_quality_trigger_lambda_name: str = "mlops-custom-data-quality-trigger"
    custom_batch_data_quality_schedule_name: str = "mlops-custom-batch-data-quality-schedule"
    custom_batch_data_quality_trigger_lambda_name: str = "mlops-custom-batch-data-quality-trigger"
    state_machine_name: str = "mlops-feedback-loop"

    lambda_execution_role_arn: str = ""
    stepfunctions_role_arn: str = ""
    eventbridge_to_sfn_role_arn: str = ""
    kms_key_arn: str = ""

    metric_namespace: str = "MLOps/Lab"
    violations_metric_name: str = "DataQualityViolations"
    batch_violations_metric_name: str = "BatchDataQualityViolations"
    model_quality_metric_namespace: str = "aws/sagemaker/Endpoints/model-metrics"
    model_quality_native_metric_name: str = "f1"
    model_quality_accuracy_metric_name: str = "ModelQualityAccuracy"
    model_quality_f1_metric_name: str = "ModelQualityF1"
    model_quality_auc_metric_name: str = "ModelQualityAUC"
    model_quality_records_metric_name: str = "ModelQualityRecords"
    alarm_threshold: float = 1.0
    alarm_period_seconds: int = 300
    alarm_evaluation_periods: int = 1
    alarm_datapoints_to_alarm: int = 1
    alarm_treat_missing_data: str = "notBreaching"
    f1_threshold: float = 0.70
    auc_threshold: float = 0.70
    model_quality_accuracy_threshold: float = 0.75
    model_quality_f1_threshold: float = 0.70
    model_quality_auc_threshold: float = 0.70
    model_quality_min_records: int = 20
    model_quality_problem_type: str = "BinaryClassification"
    model_quality_inference_attribute: str = "prediction"
    model_quality_probability_attribute: str = "probability"
    model_quality_probability_threshold: float = 0.5
    model_quality_start_time_offset: str = "-PT1H"
    model_quality_end_time_offset: str = "-PT0H"
    monitoring_cron_expression: str = "cron(0 * ? * * *)"
    model_quality_monitoring_cron_expression: str = "cron(0 * ? * * *)"
    custom_model_quality_cron_expression: str = "cron(0 * ? * * *)"
    custom_data_quality_cron_expression: str = "cron(0 * ? * * *)"
    custom_batch_data_quality_cron_expression: str = "cron(0 * ? * * *)"
    custom_model_quality_window_hours: int = 24
    custom_data_quality_window_hours: int = 24
    alarm_sns_topic_name: str = "mlops-lab-alarm-notifications"
    alarm_email: str = "enriquemejiagamarra@gmail.com"

    local_outputs_dir: Path = field(default_factory=lambda: Path("artifacts/local_outputs"))
    local_cache_dir: Path = field(default_factory=lambda: Path("data/local_cache"))

    @property
    def is_standalone(self) -> bool:
        return self.lab_mode == "standalone"

    @property
    def is_integrated(self) -> bool:
        return self.lab_mode == "integrated"

    @property
    def resource_base(self) -> str:
        return f"{self.resource_prefix}-{self.environment}"

    @property
    def s3_base_uri(self) -> str:
        if not self.s3_bucket_name:
            return ""
        return f"s3://{self.s3_bucket_name}/{self.resource_prefix}/{self.environment}"

    @property
    def data_s3_uri(self) -> str:
        if not self.s3_base_uri:
            return ""
        return f"{self.s3_base_uri}/data"

    @property
    def raw_data_s3_uri(self) -> str:
        if not self.data_s3_uri:
            return ""
        return f"{self.data_s3_uri}/raw"

    @property
    def processed_data_s3_uri(self) -> str:
        if not self.data_s3_uri:
            return ""
        return f"{self.data_s3_uri}/processed"

    @property
    def train_data_s3_uri(self) -> str:
        if not self.processed_data_s3_uri:
            return ""
        return f"{self.processed_data_s3_uri}/train/train.csv"

    @property
    def test_data_s3_uri(self) -> str:
        if not self.processed_data_s3_uri:
            return ""
        return f"{self.processed_data_s3_uri}/test/test.csv"

    @property
    def baseline_data_s3_uri(self) -> str:
        if not self.raw_data_s3_uri:
            return ""
        return f"{self.raw_data_s3_uri}/baseline.csv"

    @property
    def baseline_monitor_s3_uri(self) -> str:
        if not self.raw_data_s3_uri:
            return ""
        return f"{self.raw_data_s3_uri}/baseline_monitor.csv"

    @property
    def artifacts_s3_uri(self) -> str:
        if not self.s3_base_uri:
            return ""
        return f"{self.s3_base_uri}/artifacts"

    @property
    def evaluation_s3_uri(self) -> str:
        if not self.artifacts_s3_uri:
            return ""
        return f"{self.artifacts_s3_uri}/evaluation"

    @property
    def model_artifacts_s3_uri(self) -> str:
        if self.model_artifact_s3_uri:
            return _normalize_s3_uri(self.model_artifact_s3_uri)
        if not self.artifacts_s3_uri:
            return ""
        return f"{self.artifacts_s3_uri}/models"

    @property
    def data_capture_s3_uri(self) -> str:
        if self.data_capture_s3_uri_override:
            return _normalize_s3_uri(self.data_capture_s3_uri_override)
        if not self.s3_base_uri:
            return ""
        return f"{self.s3_base_uri}/data-capture/{self.endpoint_name}"

    @property
    def monitoring_s3_uri(self) -> str:
        if not self.s3_base_uri:
            return ""
        return f"{self.s3_base_uri}/monitoring"

    @property
    def baseline_s3_uri(self) -> str:
        if not self.monitoring_s3_uri:
            return ""
        return f"{self.monitoring_s3_uri}/baseline"

    @property
    def statistics_s3_uri(self) -> str:
        if not self.baseline_s3_uri:
            return ""
        return f"{self.baseline_s3_uri}/statistics.json"

    @property
    def constraints_s3_uri(self) -> str:
        if not self.baseline_s3_uri:
            return ""
        return f"{self.baseline_s3_uri}/constraints.json"

    @property
    def reports_s3_uri(self) -> str:
        if not self.s3_base_uri:
            return ""
        return f"{self.s3_base_uri}/reports"

    @property
    def model_quality_s3_uri(self) -> str:
        if not self.s3_base_uri:
            return ""
        return f"{self.s3_base_uri}/model-quality"

    @property
    def model_quality_predictions_s3_uri(self) -> str:
        if not self.model_quality_s3_uri:
            return ""
        return f"{self.model_quality_s3_uri}/predictions"

    @property
    def model_quality_baseline_s3_uri(self) -> str:
        if not self.model_quality_s3_uri:
            return ""
        return f"{self.model_quality_s3_uri}/baseline"

    @property
    def model_quality_baseline_dataset_s3_uri(self) -> str:
        if not self.model_quality_baseline_s3_uri:
            return ""
        return f"{self.model_quality_baseline_s3_uri}/baseline.csv"

    @property
    def model_quality_constraints_s3_uri(self) -> str:
        if not self.model_quality_baseline_s3_uri:
            return ""
        return f"{self.model_quality_baseline_s3_uri}/constraints.json"

    @property
    def model_quality_statistics_s3_uri(self) -> str:
        if not self.model_quality_baseline_s3_uri:
            return ""
        return f"{self.model_quality_baseline_s3_uri}/statistics.json"

    @property
    def model_quality_ground_truth_s3_uri(self) -> str:
        if not self.model_quality_s3_uri:
            return ""
        return f"{self.model_quality_s3_uri}/ground-truth"

    @property
    def model_quality_ground_truth_debug_s3_uri(self) -> str:
        if not self.model_quality_s3_uri:
            return ""
        return f"{self.model_quality_s3_uri}/ground-truth-debug"

    @property
    def model_quality_reports_s3_uri(self) -> str:
        if not self.model_quality_s3_uri:
            return ""
        return f"{self.model_quality_s3_uri}/reports"

    @property
    def custom_model_quality_s3_uri(self) -> str:
        if not self.model_quality_s3_uri:
            return ""
        return f"{self.model_quality_s3_uri}/custom"

    @property
    def custom_model_quality_code_s3_uri(self) -> str:
        if not self.custom_model_quality_s3_uri:
            return ""
        return f"{self.custom_model_quality_s3_uri}/code"

    @property
    def custom_model_quality_reports_s3_uri(self) -> str:
        if not self.custom_model_quality_s3_uri:
            return ""
        return f"{self.custom_model_quality_s3_uri}/reports"

    @property
    def custom_data_quality_s3_uri(self) -> str:
        if not self.monitoring_s3_uri:
            return ""
        return f"{self.monitoring_s3_uri}/custom"

    @property
    def custom_data_quality_code_s3_uri(self) -> str:
        if not self.custom_data_quality_s3_uri:
            return ""
        return f"{self.custom_data_quality_s3_uri}/code"

    @property
    def custom_batch_data_quality_s3_uri(self) -> str:
        if not self.s3_base_uri:
            return ""
        return f"{self.s3_base_uri}/batch-transform/custom-monitoring"

    @property
    def custom_batch_data_quality_reports_s3_uri(self) -> str:
        if not self.custom_batch_data_quality_s3_uri:
            return ""
        return f"{self.custom_batch_data_quality_s3_uri}/reports"

    @property
    def custom_batch_data_quality_code_s3_uri(self) -> str:
        if not self.custom_batch_data_quality_s3_uri:
            return ""
        return f"{self.custom_batch_data_quality_s3_uri}/code"

    @property
    def custom_data_quality_reports_s3_uri(self) -> str:
        if not self.custom_data_quality_s3_uri:
            return ""
        return f"{self.custom_data_quality_s3_uri}/reports"

    @property
    def endpoint_config_name(self) -> str:
        return f"{self.endpoint_name}-config"

    @property
    def sagemaker_model_name(self) -> str:
        return f"{self.endpoint_name}-model"

    @property
    def sagemaker_batch_model_name(self) -> str:
        return f"{self.resource_base}-batch-model"

    @property
    def batch_transform_input_s3_uri(self) -> str:
        override = _env("BATCH_TRANSFORM_INPUT_S3_URI")
        if override:
            return _normalize_s3_uri(override)
        if not self.raw_data_s3_uri:
            return ""
        return f"{self.raw_data_s3_uri}/inference_normal.jsonl"

    @property
    def batch_transform_output_s3_uri(self) -> str:
        override = _env("BATCH_TRANSFORM_OUTPUT_S3_URI")
        if override:
            return _normalize_s3_uri(override)
        if not self.s3_base_uri:
            return ""
        return f"{self.s3_base_uri}/batch-transform/output"

    @property
    def batch_data_capture_s3_uri(self) -> str:
        override = _env("BATCH_DATA_CAPTURE_S3_URI")
        if override:
            return _normalize_s3_uri(override)
        if not self.s3_base_uri:
            return ""
        return f"{self.s3_base_uri}/batch-transform/data-capture"

    @property
    def batch_monitoring_s3_uri(self) -> str:
        override = _env("BATCH_MONITORING_S3_URI")
        if override:
            return _normalize_s3_uri(override)
        if not self.s3_base_uri:
            return ""
        return f"{self.s3_base_uri}/batch-transform/monitoring"

    @property
    def batch_monitoring_schedule_name(self) -> str:
        return _env("BATCH_MONITORING_SCHEDULE_NAME", f"{self.resource_prefix}-batch-monitoring-schedule")

    @property
    def feedback_lambda_name(self) -> str:
        return f"{self.resource_prefix}-feedback-handler"

    @property
    def retraining_lambda_name(self) -> str:
        return f"{self.resource_prefix}-retraining-trigger"

    @property
    def rollback_lambda_name(self) -> str:
        return f"{self.resource_prefix}-rollback-handler"

    @property
    def baseline_update_lambda_name(self) -> str:
        return f"{self.resource_prefix}-baseline-update-handler"

    @property
    def human_review_lambda_name(self) -> str:
        return f"{self.resource_prefix}-human-review-handler"

    @property
    def eventbridge_rule_name(self) -> str:
        return f"{self.resource_prefix}-alarm-to-feedback-loop"

    @staticmethod
    def _candidate_list(preferred: str, candidates: str, fallback_candidates: str = "") -> list[str]:
        values: list[str] = []
        for item in [*_csv_values(candidates), preferred, *_csv_values(fallback_candidates)]:
            if item and item not in values:
                values.append(item)
        return values

    @property
    def endpoint_instance_type_candidates(self) -> list[str]:
        return self._candidate_list(self.instance_type, self.instance_type_candidates, DEFAULT_ENDPOINT_INSTANCE_TYPE_CANDIDATES)

    @property
    def training_instance_type_candidates_list(self) -> list[str]:
        return self._candidate_list(self.training_instance_type, self.training_instance_type_candidates, DEFAULT_TRAINING_INSTANCE_TYPE_CANDIDATES)

    @property
    def processing_instance_type_candidates_list(self) -> list[str]:
        return self._candidate_list(self.processing_instance_type, self.processing_instance_type_candidates, DEFAULT_PROCESSING_INSTANCE_TYPE_CANDIDATES)

    @property
    def model_monitor_processing_instance_type_candidates_list(self) -> list[str]:
        return self._candidate_list(
            self.model_monitor_processing_instance_type,
            self.model_monitor_processing_instance_type_candidates,
            DEFAULT_MODEL_MONITOR_PROCESSING_INSTANCE_TYPE_CANDIDATES,
        )

    @property
    def batch_transform_instance_type_candidates_list(self) -> list[str]:
        return self._candidate_list(self.instance_type, self.batch_transform_instance_type_candidates, DEFAULT_BATCH_TRANSFORM_INSTANCE_TYPE_CANDIDATES)

    @property
    def tags(self) -> list[dict[str, str]]:
        return [
            {"Key": "Project", "Value": "MLOpsAWS"},
            {"Key": "Environment", "Value": self.environment.title()},
            {"Key": "Owner", "Value": "Student"},
            {"Key": "ManagedBy", "Value": "IaC"},
            {"Key": "CostCenter", "Value": "Training"},
            {"Key": "AutoDelete", "Value": "true"},
        ]

    def ensure_local_dirs(self) -> None:
        self.local_outputs_dir.mkdir(parents=True, exist_ok=True)
        self.local_cache_dir.mkdir(parents=True, exist_ok=True)

    def metadata_path(self, name: str) -> Path:
        safe_name = name if name.endswith(".json") else f"{name}.json"
        return self.local_outputs_dir / safe_name

    def require(self, fields: Iterable[str]) -> None:
        missing = [field for field in fields if not getattr(self, field)]
        if missing:
            joined = ", ".join(missing)
            raise ConfigError(f"Missing required configuration: {joined}. Check .env or environment variables.")

    def validate_for_cloud(self, require_execution_role: bool = False) -> None:
        self.require(["aws_region", "s3_bucket_name"])
        if require_execution_role:
            self.require(["sagemaker_execution_role_arn"])

    def external_resource_names(self) -> set[str]:
        external = set()
        if self.is_integrated:
            for value in [
                self.model_package_group_name,
                self.model_package_arn,
                self.model_artifact_s3_uri,
                self.model_image_uri,
                self.endpoint_name,
                self.feature_group_name,
                self.feature_contract_s3_uri,
                self.data_capture_s3_uri_override,
            ]:
                if value:
                    external.add(value)
        return external


def load_config(validate: bool = False, require_execution_role: bool = False) -> LabConfig:
    _load_dotenv()

    lab_mode = _env("LAB_MODE", "standalone").lower()
    if lab_mode not in VALID_LAB_MODES:
        allowed = ", ".join(sorted(VALID_LAB_MODES))
        raise ConfigError(f"LAB_MODE must be one of: {allowed}. Got: {lab_mode}")

    config = LabConfig(
        lab_mode=lab_mode,
        aws_profile=_env("AWS_PROFILE"),
        aws_region=_env("AWS_REGION", "us-east-1"),
        project_name=_env("PROJECT_NAME", "mlops-aws"),
        environment=_env("ENVIRONMENT", "lab"),
        resource_prefix=safe_name(_env("RESOURCE_PREFIX", "mlops-lab")),
        s3_bucket_name=_env("S3_BUCKET_NAME"),
        sagemaker_execution_role_arn=_env("SAGEMAKER_EXECUTION_ROLE_ARN"),
        model_package_group_name=_env("MODEL_PACKAGE_GROUP_NAME", "mlops-model-package-group"),
        model_package_arn=_env("MODEL_PACKAGE_ARN"),
        model_artifact_s3_uri=_env("MODEL_ARTIFACT_S3_URI"),
        model_image_uri=_env("MODEL_IMAGE_URI"),
        model_monitor_image_uri=_env("MODEL_MONITOR_IMAGE_URI"),
        endpoint_name=_env("ENDPOINT_NAME", "mlops-lab-endpoint"),
        feature_group_name=_env("FEATURE_GROUP_NAME"),
        feature_contract_s3_uri=_env("FEATURE_CONTRACT_S3_URI"),
        data_capture_s3_uri_override=_env("DATA_CAPTURE_S3_URI"),
        create_standalone_dataset=_bool_env("CREATE_STANDALONE_DATASET", True),
        create_standalone_model=_bool_env("CREATE_STANDALONE_MODEL", True),
        create_endpoint=_bool_env("CREATE_ENDPOINT", True),
        enable_data_capture=_bool_env("ENABLE_DATA_CAPTURE", True),
        capture_endpoint_output=_bool_env("CAPTURE_ENDPOINT_OUTPUT", True),
        enable_model_monitor=_bool_env("ENABLE_MODEL_MONITOR", True),
        enable_cloudwatch_alarm=_bool_env("ENABLE_CLOUDWATCH_ALARM", True),
        enable_eventbridge=_bool_env("ENABLE_EVENTBRIDGE", True),
        enable_feedback_loop=_bool_env("ENABLE_FEEDBACK_LOOP", True),
        enable_automatic_retraining=_bool_env("ENABLE_AUTOMATIC_RETRAINING", False),
        enable_rollback_execution=_bool_env("ENABLE_ROLLBACK_EXECUTION", False),
        enable_baseline_update=_bool_env("ENABLE_BASELINE_UPDATE", False),
        auto_select_compute=_bool_env("AUTO_SELECT_COMPUTE", True),
        instance_type=_env("INSTANCE_TYPE", "ml.m5.large"),
        training_instance_type=_env("TRAINING_INSTANCE_TYPE", "ml.m5.large"),
        processing_instance_type=_env("PROCESSING_INSTANCE_TYPE", "ml.m5.large"),
        model_monitor_processing_instance_type=_env("MODEL_MONITOR_PROCESSING_INSTANCE_TYPE", "ml.m6i.large"),
        instance_type_candidates=_env("INSTANCE_TYPE_CANDIDATES", DEFAULT_ENDPOINT_INSTANCE_TYPE_CANDIDATES),
        training_instance_type_candidates=_env("TRAINING_INSTANCE_TYPE_CANDIDATES", DEFAULT_TRAINING_INSTANCE_TYPE_CANDIDATES),
        processing_instance_type_candidates=_env("PROCESSING_INSTANCE_TYPE_CANDIDATES", DEFAULT_PROCESSING_INSTANCE_TYPE_CANDIDATES),
        model_monitor_processing_instance_type_candidates=_env(
            "MODEL_MONITOR_PROCESSING_INSTANCE_TYPE_CANDIDATES",
            DEFAULT_MODEL_MONITOR_PROCESSING_INSTANCE_TYPE_CANDIDATES,
        ),
        batch_transform_instance_type_candidates=_env("BATCH_TRANSFORM_INSTANCE_TYPE_CANDIDATES", DEFAULT_BATCH_TRANSFORM_INSTANCE_TYPE_CANDIDATES),
        pipeline_name=_env("PIPELINE_NAME", "mlops-build-pipeline"),
        monitoring_schedule_name=_env("MONITORING_SCHEDULE_NAME", "mlops-monitoring-schedule"),
        alarm_name=_env("ALARM_NAME", "mlops-data-quality-alarm"),
        model_quality_schedule_name=_env("MODEL_QUALITY_SCHEDULE_NAME", "mlops-model-quality-schedule"),
        model_quality_job_definition_name=_env("MODEL_QUALITY_JOB_DEFINITION_NAME", "mlops-model-quality-job-def"),
        model_quality_alarm_name=_env("MODEL_QUALITY_ALARM_NAME", "mlops-model-quality-alarm"),
        custom_data_quality_alarm_name=_env("CUSTOM_DATA_QUALITY_ALARM_NAME", "mlops-custom-data-quality-alarm"),
        custom_batch_data_quality_alarm_name=_env("CUSTOM_BATCH_DATA_QUALITY_ALARM_NAME", "mlops-custom-batch-data-quality-alarm"),
        custom_model_quality_alarm_name=_env("CUSTOM_MODEL_QUALITY_ALARM_NAME", "mlops-custom-model-quality-alarm"),
        custom_model_quality_schedule_name=_env("CUSTOM_MODEL_QUALITY_SCHEDULE_NAME", "mlops-custom-model-quality-schedule"),
        custom_model_quality_trigger_lambda_name=_env("CUSTOM_MODEL_QUALITY_TRIGGER_LAMBDA_NAME", "mlops-custom-model-quality-trigger"),
        custom_data_quality_schedule_name=_env("CUSTOM_DATA_QUALITY_SCHEDULE_NAME", "mlops-custom-data-quality-schedule"),
        custom_data_quality_trigger_lambda_name=_env("CUSTOM_DATA_QUALITY_TRIGGER_LAMBDA_NAME", "mlops-custom-data-quality-trigger"),
        custom_batch_data_quality_schedule_name=_env(
            "CUSTOM_BATCH_DATA_QUALITY_SCHEDULE_NAME",
            "mlops-custom-batch-data-quality-schedule",
        ),
        custom_batch_data_quality_trigger_lambda_name=_env(
            "CUSTOM_BATCH_DATA_QUALITY_TRIGGER_LAMBDA_NAME",
            "mlops-custom-batch-data-quality-trigger",
        ),
        state_machine_name=_env("STATE_MACHINE_NAME", "mlops-feedback-loop"),
        lambda_execution_role_arn=_env("LAMBDA_EXECUTION_ROLE_ARN"),
        stepfunctions_role_arn=_env("STEPFUNCTIONS_ROLE_ARN"),
        eventbridge_to_sfn_role_arn=_env("EVENTBRIDGE_TO_SFN_ROLE_ARN"),
        kms_key_arn=_env("KMS_KEY_ARN"),
        metric_namespace=_env("METRIC_NAMESPACE", "MLOps/Lab"),
        violations_metric_name=_env("VIOLATIONS_METRIC_NAME", "DataQualityViolations"),
        batch_violations_metric_name=_env("BATCH_VIOLATIONS_METRIC_NAME", "BatchDataQualityViolations"),
        model_quality_metric_namespace=_env("MODEL_QUALITY_METRIC_NAMESPACE", "aws/sagemaker/Endpoints/model-metrics"),
        model_quality_native_metric_name=_env("MODEL_QUALITY_NATIVE_METRIC_NAME", "f1"),
        model_quality_accuracy_metric_name=_env("MODEL_QUALITY_ACCURACY_METRIC_NAME", "ModelQualityAccuracy"),
        model_quality_f1_metric_name=_env("MODEL_QUALITY_F1_METRIC_NAME", "ModelQualityF1"),
        model_quality_auc_metric_name=_env("MODEL_QUALITY_AUC_METRIC_NAME", "ModelQualityAUC"),
        model_quality_records_metric_name=_env("MODEL_QUALITY_RECORDS_METRIC_NAME", "ModelQualityRecords"),
        alarm_threshold=float(_env("ALARM_THRESHOLD", "1.0")),
        alarm_period_seconds=int(_env("ALARM_PERIOD_SECONDS", "300")),
        alarm_evaluation_periods=int(_env("ALARM_EVALUATION_PERIODS", "1")),
        alarm_datapoints_to_alarm=int(_env("ALARM_DATAPOINTS_TO_ALARM", "1")),
        alarm_treat_missing_data=_env("ALARM_TREAT_MISSING_DATA", "notBreaching"),
        f1_threshold=float(_env("F1_THRESHOLD", "0.70")),
        auc_threshold=float(_env("AUC_THRESHOLD", "0.70")),
        model_quality_accuracy_threshold=float(_env("MODEL_QUALITY_ACCURACY_THRESHOLD", "0.75")),
        model_quality_f1_threshold=float(_env("MODEL_QUALITY_F1_THRESHOLD", "0.70")),
        model_quality_auc_threshold=float(_env("MODEL_QUALITY_AUC_THRESHOLD", "0.70")),
        model_quality_min_records=int(_env("MODEL_QUALITY_MIN_RECORDS", "20")),
        model_quality_problem_type=_env("MODEL_QUALITY_PROBLEM_TYPE", "BinaryClassification"),
        model_quality_inference_attribute=_env("MODEL_QUALITY_INFERENCE_ATTRIBUTE", "prediction"),
        model_quality_probability_attribute=_env("MODEL_QUALITY_PROBABILITY_ATTRIBUTE", "probability"),
        model_quality_probability_threshold=float(_env("MODEL_QUALITY_PROBABILITY_THRESHOLD", "0.5")),
        model_quality_start_time_offset=_env("MODEL_QUALITY_START_TIME_OFFSET", "-PT1H"),
        model_quality_end_time_offset=_env("MODEL_QUALITY_END_TIME_OFFSET", "-PT0H"),
        monitoring_cron_expression=_env("MONITORING_CRON_EXPRESSION", "cron(0 * ? * * *)"),
        model_quality_monitoring_cron_expression=_env("MODEL_QUALITY_MONITORING_CRON_EXPRESSION", "cron(0 * ? * * *)"),
        custom_model_quality_cron_expression=_env(
            "CUSTOM_MODEL_QUALITY_CRON_EXPRESSION",
            _env("MODEL_QUALITY_MONITORING_CRON_EXPRESSION", "cron(0 * ? * * *)"),
        ),
        custom_data_quality_cron_expression=_env(
            "CUSTOM_DATA_QUALITY_CRON_EXPRESSION",
            _env("MONITORING_CRON_EXPRESSION", "cron(0 * ? * * *)"),
        ),
        custom_batch_data_quality_cron_expression=_env(
            "CUSTOM_BATCH_DATA_QUALITY_CRON_EXPRESSION",
            _env("MONITORING_CRON_EXPRESSION", "cron(0 * ? * * *)"),
        ),
        custom_model_quality_window_hours=int(_env("CUSTOM_MODEL_QUALITY_WINDOW_HOURS", "24")),
        custom_data_quality_window_hours=int(_env("CUSTOM_DATA_QUALITY_WINDOW_HOURS", "24")),
        alarm_sns_topic_name=_env("ALARM_SNS_TOPIC_NAME", "mlops-lab-alarm-notifications"),
        alarm_email=_env("ALARM_EMAIL", "enriquemejiagamarra@gmail.com"),
    )

    if validate:
        config.validate_for_cloud(require_execution_role=require_execution_role)
    config.ensure_local_dirs()
    return config


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
    return path


def read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default or {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_metadata(config: LabConfig, name: str, payload: dict[str, Any]) -> Path:
    enriched = {
        "generated_at": utc_now_iso(),
        "lab_mode": config.lab_mode,
        "project_name": config.project_name,
        "environment": config.environment,
        **payload,
    }
    return write_json(config.metadata_path(name), enriched)


def read_metadata(config: LabConfig, name: str) -> dict[str, Any]:
    return read_json(config.metadata_path(name))


def main() -> None:
    config = load_config(validate=False)
    printable = {
        "lab_mode": config.lab_mode,
        "aws_profile": config.aws_profile,
        "aws_region": config.aws_region,
        "s3_bucket_name": config.s3_bucket_name or "PENDING - set S3_BUCKET_NAME or run make deploy-infra",
        "pipeline_name": config.pipeline_name,
        "model_package_group_name": config.model_package_group_name,
        "endpoint_name": config.endpoint_name,
        "data_capture_s3_uri": config.data_capture_s3_uri or "PENDING - requires S3_BUCKET_NAME",
        "monitoring_schedule_name": config.monitoring_schedule_name,
        "alarm_name": config.alarm_name,
        "model_quality_schedule_name": config.model_quality_schedule_name,
        "model_quality_alarm_name": config.model_quality_alarm_name,
        "custom_data_quality_alarm_name": config.custom_data_quality_alarm_name,
        "custom_batch_data_quality_alarm_name": config.custom_batch_data_quality_alarm_name,
        "custom_model_quality_alarm_name": config.custom_model_quality_alarm_name,
        "custom_model_quality_schedule_name": config.custom_model_quality_schedule_name,
        "custom_model_quality_trigger_lambda_name": config.custom_model_quality_trigger_lambda_name,
        "custom_data_quality_schedule_name": config.custom_data_quality_schedule_name,
        "custom_data_quality_trigger_lambda_name": config.custom_data_quality_trigger_lambda_name,
        "custom_batch_data_quality_schedule_name": config.custom_batch_data_quality_schedule_name,
        "custom_batch_data_quality_trigger_lambda_name": config.custom_batch_data_quality_trigger_lambda_name,
        "state_machine_name": config.state_machine_name,
        "enable_automatic_retraining": config.enable_automatic_retraining,
        "capture_endpoint_output": config.capture_endpoint_output,
        "model_quality_s3_uri": config.model_quality_s3_uri or "PENDING - requires S3_BUCKET_NAME",
        "model_quality_ground_truth_s3_uri": config.model_quality_ground_truth_s3_uri or "PENDING - requires S3_BUCKET_NAME",
        "custom_model_quality_reports_s3_uri": config.custom_model_quality_reports_s3_uri or "PENDING - requires S3_BUCKET_NAME",
        "custom_data_quality_reports_s3_uri": config.custom_data_quality_reports_s3_uri or "PENDING - requires S3_BUCKET_NAME",
        "custom_batch_data_quality_reports_s3_uri": config.custom_batch_data_quality_reports_s3_uri or "PENDING - requires S3_BUCKET_NAME",
        "model_quality_native_metric": {
            "namespace": config.model_quality_metric_namespace,
            "metric_name": config.model_quality_native_metric_name,
        },
        "alarm_notifications": {
            "topic_name": config.alarm_sns_topic_name,
            "email": config.alarm_email,
        },
        "model_quality_thresholds": {
            "accuracy": config.model_quality_accuracy_threshold,
            "f1": config.model_quality_f1_threshold,
            "auc": config.model_quality_auc_threshold,
            "min_records": config.model_quality_min_records,
        },
        "auto_select_compute": config.auto_select_compute,
        "processing_instance_type_candidates": config.processing_instance_type_candidates_list,
        "model_monitor_processing_instance_type_candidates": config.model_monitor_processing_instance_type_candidates_list,
        "training_instance_type_candidates": config.training_instance_type_candidates_list,
        "endpoint_instance_type_candidates": config.endpoint_instance_type_candidates,
        "batch_transform_instance_type_candidates": config.batch_transform_instance_type_candidates_list,
    }
    print(json.dumps(printable, indent=2))


if __name__ == "__main__":
    main()
