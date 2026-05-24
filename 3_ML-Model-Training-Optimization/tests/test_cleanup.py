from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_destroy_infra_empties_stack_owned_bucket_before_delete() -> None:
    source = (PROJECT_ROOT / "src" / "destroy_infra.py").read_text(encoding="utf-8")

    assert "empty_stack_bucket_if_owned(config, cf)" in source
    assert "describe_stack_resource" in source
    assert "LogicalResourceId=\"LabBucket\"" in source
    assert "delete_s3_objects(config)" in source


def test_destroy_scripts_delegate_to_python_destroy_infra() -> None:
    bash_source = (PROJECT_ROOT / "scripts" / "destroy_infra.sh").read_text(encoding="utf-8")
    ps_source = (PROJECT_ROOT / "scripts" / "destroy_infra.ps1").read_text(encoding="utf-8")

    assert "python -m src.destroy_infra" in bash_source
    assert "python -m src.destroy_infra" in ps_source


def test_cleanup_s3_delete_handles_versioned_objects() -> None:
    source = (PROJECT_ROOT / "src" / "cleanup_resources.py").read_text(encoding="utf-8")

    assert "list_object_versions" in source
    assert "DeleteMarkers" in source
    assert "VersionId" in source
