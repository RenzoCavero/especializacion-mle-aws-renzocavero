"""Deployment pipeline facade: approved model -> endpoint -> smoke test."""

from __future__ import annotations

from src.deploy_model import deploy
from src.smoke_test_endpoint import smoke_test


def deploy_approved_model(wait: bool = False, run_smoke_test: bool = True) -> dict[str, object]:
    deployment = deploy(wait=wait)
    smoke = smoke_test() if run_smoke_test and not deployment.get("skipped") else {}
    return {"deployment": deployment, "smoke_test": smoke}


if __name__ == "__main__":
    print(deploy_approved_model(wait=False, run_smoke_test=False))

