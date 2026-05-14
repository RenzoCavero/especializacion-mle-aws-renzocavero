from __future__ import annotations

import json
import logging

from botocore.exceptions import ClientError

from src.aws_clients import client, list_s3_keys
from src.config import get_config
from src.logging_utils import configure_logging
from src.state import load_state


LOGGER = logging.getLogger(__name__)


def safe_call(name: str, fn):
    try:
        return {"ok": True, "result": fn()}
    except Exception as exc:  # noqa: BLE001 - validation should collect all failures.
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    state = load_state()
    sm = client(config, "sagemaker")

    validations = {
        "feature_group": safe_call(
            "feature_group",
            lambda: sm.describe_feature_group(FeatureGroupName=config.feature_group_name),
        ),
        "s3_raw": safe_call("s3_raw", lambda: list_s3_keys(config, f"s3://{config.s3_bucket_name}/raw/", 5)),
        "s3_train": safe_call("s3_train", lambda: list_s3_keys(config, config.train_s3_uri, 5)),
        "s3_reports": safe_call("s3_reports", lambda: list_s3_keys(config, config.reports_s3_uri, 10)),
        "model_packages": safe_call(
            "model_packages",
            lambda: sm.list_model_packages(ModelPackageGroupName=config.model_package_group_name, MaxResults=10),
        ),
        "endpoints_with_prefix": safe_call(
            "endpoints_with_prefix",
            lambda: sm.list_endpoints(NameContains=config.resource_prefix, MaxResults=10).get("Endpoints", []),
        ),
    }
    endpoints = validations["endpoints_with_prefix"].get("result", [])
    validations["no_persistent_endpoints"] = {
        "ok": not endpoints,
        "result": "No SageMaker endpoints found for lab prefix." if not endpoints else endpoints,
    }
    for key in ("processing_job_name", "baseline_training_job_name", "hpo_job_name"):
        if state.get(key):
            job_name = state[key]
            if key == "processing_job_name":
                validations[key] = safe_call(key, lambda job_name=job_name: sm.describe_processing_job(ProcessingJobName=job_name))
            elif key == "baseline_training_job_name":
                validations[key] = safe_call(key, lambda job_name=job_name: sm.describe_training_job(TrainingJobName=job_name))
            else:
                validations[key] = safe_call(
                    key,
                    lambda job_name=job_name: sm.describe_hyper_parameter_tuning_job(
                        HyperParameterTuningJobName=job_name
                    ),
                )
    local_path = config.local_outputs_dir / "validation_report.json"
    local_path.write_text(json.dumps(validations, indent=2, default=str), encoding="utf-8")
    LOGGER.info("Validation report written to %s", local_path)
    failed = [name for name, result in validations.items() if not result.get("ok")]
    if failed:
        raise SystemExit(f"Validation completed with failures: {failed}. See {local_path}")
    print(json.dumps({"status": "ok", "report": str(local_path)}, indent=2))


if __name__ == "__main__":
    main()
