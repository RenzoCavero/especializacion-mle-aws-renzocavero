"""Reject a model package in SageMaker Model Registry."""

from __future__ import annotations

import argparse
import json

from .approve_model import _candidate_arn
from .aws_clients import create_clients
from .config import load_config, write_metadata


def reject(model_package_arn: str = "", reason: str = "Rejected by lab approval gate.") -> dict:
    config = load_config(validate=True)
    clients = create_clients(config)
    arn = _candidate_arn(config, clients, model_package_arn)
    clients.sagemaker.update_model_package(
        ModelPackageArn=arn,
        ModelApprovalStatus="Rejected",
        ApprovalDescription=reason[:1024],
    )
    payload = {"model_package_arn": arn, "approval_status": "Rejected", "reason": reason}
    write_metadata(config, "model_rejection", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-package-arn", default="")
    parser.add_argument("--reason", default="Rejected by lab approval gate.")
    args = parser.parse_args()
    print(json.dumps(reject(args.model_package_arn, args.reason), indent=2))


if __name__ == "__main__":
    main()

