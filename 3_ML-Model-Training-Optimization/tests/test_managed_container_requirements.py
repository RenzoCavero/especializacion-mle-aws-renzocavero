from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _installable_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_training_requirements_do_not_upgrade_managed_container_dependencies() -> None:
    assert _installable_lines(PROJECT_ROOT / "training" / "requirements.txt") == []


def test_processing_requirements_do_not_upgrade_managed_container_dependencies() -> None:
    assert _installable_lines(PROJECT_ROOT / "processing" / "requirements.txt") == []
