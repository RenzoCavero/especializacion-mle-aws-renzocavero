from __future__ import annotations

import argparse
import json

from fraud_lab.aws.event_bus import SqsPredictionEventBus
from fraud_lab.aws.feature_store import AwsFeatureStore
from fraud_lab.aws.s3_data_lake import S3DataLake
from fraud_lab.pipelines.async_update_online_features import _updated_records
from fraud_lab.pipelines.cleaned_to_curated import enrich


def async_update_online_features_aws(max_messages: int = 10) -> dict[str, int]:
    event_bus = SqsPredictionEventBus()
    feature_store = AwsFeatureStore()
    s3_lake = S3DataLake(feature_store.config, feature_store.clients)
    processed = 0

    for message in event_bus.receive(max_messages=max_messages):
        event = message["body"]
        raw = event["raw_event"]
        cleaned = event["cleaned_event"]
        prediction = event["prediction_event"]
        curated = enrich(cleaned)
        base_name = f"{cleaned['transaction_id']}_{prediction['request_id']}.json"
        s3_lake.put_json(("lake", "raw", "async-transactions", base_name), raw)
        s3_lake.put_json(("lake", "cleaned", "async-transactions", base_name), cleaned)
        s3_lake.put_json(("lake", "curated", "async-transactions", base_name), curated)

        for group, record in _updated_records(cleaned, feature_store).items():
            feature_store.put_record(group, record)
            feature_store.append_offline_export(group, [record])

        event_bus.delete(message["receipt_handle"])
        processed += 1

    summary = {"processed_events": processed}
    s3_lake.put_json(("events", "async_update_summary.json"), summary)
    print("Actualizacion asincrona cloud:")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process fraud prediction events from SQS and update lake/features."
    )
    parser.add_argument("--max-messages", type=int, default=10)
    args = parser.parse_args()
    async_update_online_features_aws(args.max_messages)


if __name__ == "__main__":
    main()

