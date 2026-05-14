from __future__ import annotations

import argparse
import json
import logging

import pandas as pd

from src.aws_clients import client
from src.config import get_config
from src.feature_schema import INFERENCE_FEATURES, TARGET_COLUMN
from src.logging_utils import configure_logging
from src.state import load_state, update_state


LOGGER = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate SageMaker Feature Store Online Store with GetRecord.")
    parser.add_argument("--customer-id", default=None)
    args = parser.parse_args()

    configure_logging()
    config = get_config()
    config.require_aws_fields()
    state = load_state()
    customer_id = args.customer_id or state.get("sample_customer_id")
    if not customer_id and config.raw_data_local_path.exists():
        customer_id = str(pd.read_csv(config.raw_data_local_path, usecols=["customer_id"]).iloc[0]["customer_id"])
    if not customer_id:
        raise ValueError("No customer id provided and no generated dataset/state found.")

    runtime = client(config, "sagemaker-featurestore-runtime")
    response = runtime.get_record(
        FeatureGroupName=config.feature_group_name,
        RecordIdentifierValueAsString=customer_id,
    )
    record = {item["FeatureName"]: item.get("ValueAsString") for item in response.get("Record", [])}
    missing = [name for name in INFERENCE_FEATURES if name not in record]
    if missing:
        raise RuntimeError(f"Online Store record is missing inference features: {missing}")

    payload = {name: record[name] for name in INFERENCE_FEATURES}
    output_path = config.local_outputs_dir / "online_store_get_record.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "customer_id": customer_id,
                "feature_group_name": config.feature_group_name,
                "record": record,
                "future_realtime_payload_without_target": payload,
                "target_present_for_training_only": TARGET_COLUMN in record,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    update_state(sample_customer_id=customer_id, online_store_validation_path=str(output_path))
    LOGGER.info("Validated Online Store GetRecord for %s", customer_id)
    LOGGER.info("Wrote validation output to %s", output_path)


if __name__ == "__main__":
    main()
