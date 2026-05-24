from __future__ import annotations

from src.instance_types import (
    instance_suffix,
    is_resource_limit_error,
    job_name_with_instance,
    parse_instance_type_list,
    unique_instance_types,
)


def test_parse_instance_type_list_trims_empty_values() -> None:
    assert parse_instance_type_list(" ml.t3.medium, ,ml.m5.large ") == (
        "ml.t3.medium",
        "ml.m5.large",
    )


def test_unique_instance_types_keeps_primary_first() -> None:
    assert unique_instance_types("ml.m5.large", ["ml.t3.medium", "ml.m5.large"]) == (
        "ml.m5.large",
        "ml.t3.medium",
    )


def test_job_name_with_instance_respects_max_length() -> None:
    name = job_name_with_instance("ml-training-opt-lab-processing-20260513220320", "ml.t3.medium", 32)
    assert len(name) <= 32
    assert name.endswith("-t3-medium")


def test_instance_suffix_is_sagemaker_job_name_safe() -> None:
    assert instance_suffix("ml.m5.xlarge") == "m5-xlarge"


def test_is_resource_limit_error_uses_message_fallback() -> None:
    exc = RuntimeError("ResourceLimitExceeded: account-level service limit is 0 Instances")
    assert is_resource_limit_error(exc)
