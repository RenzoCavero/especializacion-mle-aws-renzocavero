from __future__ import annotations

import argparse
import json

from src.aws_clients import client_error_code

from fraud_lab.aws.deploy_endpoint import cleanup_fraud_endpoint_resources
from fraud_lab.aws.feature_store import AwsFeatureStore
from fraud_lab.feature_store.feature_groups import FEATURE_GROUPS


def cleanup_feature_store_aws() -> dict[str, dict[str, list[str]]]:
    endpoint_result = cleanup_fraud_endpoint_resources()
    store = AwsFeatureStore()
    deleted: list[str] = []
    skipped: list[str] = []
    for logical_group in FEATURE_GROUPS:
        physical_name = store.physical_name(logical_group)
        if not store.describe(logical_group):
            skipped.append(physical_name)
            continue
        try:
            store.sagemaker.delete_feature_group(FeatureGroupName=physical_name)
            deleted.append(physical_name)
        except Exception as exc:
            if client_error_code(exc) in {"ResourceNotFound", "ValidationException"}:
                skipped.append(physical_name)
                continue
            raise
    result = {
        "endpoint_resources": endpoint_result,
        "feature_groups": {"deleted": deleted, "skipped": skipped},
    }
    print("Cleanup fraud cloud solicitado:")
    print(json.dumps(result, indent=2, sort_keys=True))
    print("DynamoDB, SQS, bucket y Model Registry pertenecen al stack/gobierno; no se borran aqui.")
    return result


def main() -> None:
    argparse.ArgumentParser(
        description="Delete fraud endpoint resources and Feature Groups created by the AWS fraud lab."
    ).parse_args()
    cleanup_feature_store_aws()


if __name__ == "__main__":
    main()
