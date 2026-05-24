from __future__ import annotations

from pathlib import Path

import pytest

import src.cleanup_local_outputs as local_cleanup


class FakeConfig:
    lab_mode = "standalone"
    project_name = "mlops-aws"
    environment = "test"
    local_outputs_dir = Path("artifacts/local_outputs")
    local_cache_dir = Path("data/local_cache")

    def __init__(self, root: Path) -> None:
        self.root = root

    def metadata_path(self, name: str) -> Path:
        safe_name = name if name.endswith(".json") else f"{name}.json"
        return self.root / self.local_outputs_dir / safe_name


def test_local_cleanup_dry_run_preserves_generated_files(monkeypatch, tmp_path):
    monkeypatch.setattr(local_cleanup, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(local_cleanup, "load_config", lambda validate=False: FakeConfig(tmp_path))

    output_file = tmp_path / "artifacts/local_outputs/endpoint_deployment.json"
    cache_file = tmp_path / "data/local_cache/churn_train.csv"
    output_file.parent.mkdir(parents=True)
    cache_file.parent.mkdir(parents=True)
    output_file.write_text("{}", encoding="utf-8")
    cache_file.write_text("record_id\n1\n", encoding="utf-8")

    result = local_cleanup.cleanup_local_outputs(execute=False)

    assert result["executed"] is False
    assert output_file.exists()
    assert cache_file.exists()
    assert (tmp_path / "artifacts/local_outputs/cleanup_local_outputs_plan.json").exists()
    assert result["targets"][0]["items"][0]["status"] == "would_delete"


def test_local_cleanup_execute_deletes_only_generated_contents(monkeypatch, tmp_path):
    monkeypatch.setattr(local_cleanup, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(local_cleanup, "load_config", lambda validate=False: FakeConfig(tmp_path))

    output_file = tmp_path / "artifacts/local_outputs/endpoint_deployment.json"
    cache_file = tmp_path / "data/local_cache/churn_train.csv"
    output_file.parent.mkdir(parents=True)
    cache_file.parent.mkdir(parents=True)
    output_file.write_text("{}", encoding="utf-8")
    cache_file.write_text("record_id\n1\n", encoding="utf-8")

    result = local_cleanup.cleanup_local_outputs(execute=True)

    assert result["executed"] is True
    assert not output_file.exists()
    assert not cache_file.exists()
    assert (tmp_path / "artifacts/local_outputs").is_dir()
    assert (tmp_path / "data/local_cache").is_dir()


def test_local_cleanup_refuses_paths_outside_lab_root(monkeypatch, tmp_path):
    monkeypatch.setattr(local_cleanup, "ROOT_DIR", tmp_path / "lab")

    with pytest.raises(ValueError, match="outside lab root"):
        local_cleanup._resolve_under_root(tmp_path / "outside")
