"""Configuration helpers for local scripts and AWS jobs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_DATA_DIR = DATA_DIR / "sample"
LOCAL_CACHE_DIR = DATA_DIR / "local_cache"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
LOCAL_OUTPUTS_DIR = ARTIFACTS_DIR / "local_outputs"
INFRA_DIR = PROJECT_ROOT / "infra"
TEMPLATE_PATH = INFRA_DIR / "cloudformation" / "template.yaml"


def load_dotenv(path: Path = ENV_FILE, override: bool = False) -> Dict[str, str]:
    """Load simple KEY=VALUE entries from .env without adding a dependency."""
    loaded: Dict[str, str] = {}
    if not path.exists():
        return loaded

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (override or key not in os.environ):
            os.environ[key] = value
            loaded[key] = value
    return loaded


@dataclass(frozen=True)
class Settings:
    aws_profile: Optional[str]
    aws_region: str
    project_name: str
    environment: str
    s3_bucket_name: str
    resource_prefix: str
    glue_database_name: str
    stack_name: str
    glue_job_name: str
    log_group_name: str
    glue_role_arn: str
    empty_bucket_on_destroy: bool


def get_settings(load_env: bool = True) -> Settings:
    if load_env:
        load_dotenv()

    resource_prefix = os.getenv("RESOURCE_PREFIX", "ml-data-prep-lab")
    return Settings(
        aws_profile=os.getenv("AWS_PROFILE") or None,
        aws_region=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
        project_name=os.getenv("PROJECT_NAME", "ml-data-processing-prep"),
        environment=os.getenv("ENVIRONMENT", "lab"),
        s3_bucket_name=os.getenv("S3_BUCKET_NAME", ""),
        resource_prefix=resource_prefix,
        glue_database_name=os.getenv("GLUE_DATABASE_NAME", "ml_data_prep_lab"),
        stack_name=os.getenv("STACK_NAME", f"{resource_prefix}-stack"),
        glue_job_name=os.getenv("GLUE_JOB_NAME", f"{resource_prefix}-processing-job"),
        log_group_name=os.getenv("LOG_GROUP_NAME", f"/aws/{resource_prefix}/processing"),
        glue_role_arn=os.getenv("GLUE_ROLE_ARN", ""),
        empty_bucket_on_destroy=os.getenv("EMPTY_S3_ON_DESTROY", "true").lower() == "true",
    )


def ensure_local_directories() -> None:
    for path in [SAMPLE_DATA_DIR, LOCAL_CACHE_DIR, LOCAL_OUTPUTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def s3_key(*parts: str) -> str:
    cleaned = [part.strip("/") for part in parts if part and part.strip("/")]
    return "/".join(cleaned)
