from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_model_package_version_creation_does_not_send_tags() -> None:
    source = (PROJECT_ROOT / "src" / "register_model.py").read_text(encoding="utf-8")
    create_call = source.split("response = sm.create_model_package(", 1)[1].split(
        "model_package_arn = response", 1
    )[0]

    assert "Tags=" not in create_call


def test_model_package_group_creation_keeps_lab_tags() -> None:
    source = (PROJECT_ROOT / "src" / "register_model.py").read_text(encoding="utf-8")
    group_call = source.split("sm.create_model_package_group(", 1)[1].split(
        "LOGGER.info", 1
    )[0]

    assert "Tags=LAB_TAGS" in group_call
