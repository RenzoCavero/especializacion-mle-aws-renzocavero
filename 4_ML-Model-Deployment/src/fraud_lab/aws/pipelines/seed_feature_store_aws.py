from __future__ import annotations

import argparse
import json

from fraud_lab.aws.feature_store import AwsFeatureStore


def seed_feature_store_aws() -> dict[str, object]:
    result = AwsFeatureStore().seed_feature_store()
    print("SageMaker Feature Store preparado:")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    argparse.ArgumentParser(
        description="Create and seed SageMaker Feature Store Online/Offline Stores."
    ).parse_args()
    seed_feature_store_aws()


if __name__ == "__main__":
    main()

