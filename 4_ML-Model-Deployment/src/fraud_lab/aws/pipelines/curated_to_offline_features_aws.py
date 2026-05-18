from __future__ import annotations

import argparse
import json

from fraud_lab.aws.feature_store import AwsFeatureStore


def curated_to_offline_features_aws() -> dict[str, object]:
    result = AwsFeatureStore().seed_feature_store()
    print("Curated -> SageMaker Feature Store completado:")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    argparse.ArgumentParser(
        description="Create AWS Feature Groups and seed Online/Offline Stores."
    ).parse_args()
    curated_to_offline_features_aws()


if __name__ == "__main__":
    main()

