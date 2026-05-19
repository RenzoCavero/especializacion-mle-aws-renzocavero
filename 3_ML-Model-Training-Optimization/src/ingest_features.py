from __future__ import annotations

import argparse
import logging
import math
import time

import pandas as pd

from src.aws_clients import client, upload_file
from src.config import get_config
from src.feature_schema import FEATURE_DEFINITIONS, validate_records_columns
from src.logging_utils import configure_logging
from src.state import update_state


LOGGER = logging.getLogger(__name__)


def _value_as_string(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def row_to_record(row: pd.Series) -> list[dict[str, str]]:
    return [
        {"FeatureName": feature.name, "ValueAsString": _value_as_string(row[feature.name])}
        for feature in FEATURE_DEFINITIONS
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest synthetic churn features into SageMaker Feature Store.")
    parser.add_argument("--limit", type=int, default=0, help="Optional row limit for smoke tests.")
    parser.add_argument("--sleep-every", type=int, default=250)
    args = parser.parse_args()

    configure_logging()
    config = get_config()
    config.require_aws_fields()
    input_path = config.curated_features_local_path if config.curated_features_local_path.exists() else config.raw_data_local_path
    if not input_path.exists():
        raise FileNotFoundError(
            "Run python -m src.generate_sample_data and python -m src.prepare_feature_sources before ingesting features."
        )

    df = pd.read_csv(input_path)
    validate_records_columns(list(df.columns))
    if args.limit:
        df = df.head(args.limit)

    runtime = client(config, "sagemaker-featurestore-runtime")
    for index, row in df.iterrows():
        runtime.put_record(FeatureGroupName=config.feature_group_name, Record=row_to_record(row))
        if args.sleep_every and (index + 1) % args.sleep_every == 0:
            LOGGER.info("Ingested %s records", index + 1)
            time.sleep(0.2)

    upload_file(config, str(input_path), config.feature_snapshot_s3_uri)
    update_state(
        ingested_records=int(len(df)),
        feature_snapshot_s3_uri=config.feature_snapshot_s3_uri,
        sample_customer_id=str(df.iloc[0]["customer_id"]),
    )
    LOGGER.info("Ingested %s records from %s into %s", len(df), input_path, config.feature_group_name)
    LOGGER.info("Feature snapshot for Processing Job available at %s", config.feature_snapshot_s3_uri)


if __name__ == "__main__":
    main()
