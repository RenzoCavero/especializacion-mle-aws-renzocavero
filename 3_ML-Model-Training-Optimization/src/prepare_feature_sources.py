from __future__ import annotations

import json
import logging

import pandas as pd

from src.aws_clients import put_json_s3, upload_file
from src.config import get_config
from src.feature_pipeline import clean_raw_frame, curate_cleaned_frame, feature_lineage_document
from src.logging_utils import configure_logging
from src.state import update_state


LOGGER = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    if not config.raw_data_local_path.exists():
        raise FileNotFoundError(
            f"{config.raw_data_local_path} does not exist. Run python -m src.generate_sample_data first."
        )

    raw = pd.read_csv(config.raw_data_local_path)
    cleaned, cleaning_steps = clean_raw_frame(raw)
    curated, curation_steps = curate_cleaned_frame(cleaned)

    config.cleaned_data_local_path.parent.mkdir(parents=True, exist_ok=True)
    config.curated_features_local_path.parent.mkdir(parents=True, exist_ok=True)
    config.feature_lineage_local_path.parent.mkdir(parents=True, exist_ok=True)

    cleaned.to_csv(config.cleaned_data_local_path, index=False)
    curated.to_csv(config.curated_features_local_path, index=False)

    upload_file(config, str(config.cleaned_data_local_path), config.cleaned_data_s3_uri)
    upload_file(config, str(config.curated_features_local_path), config.curated_features_s3_uri)
    upload_file(config, str(config.curated_features_local_path), config.feature_snapshot_s3_uri)

    lineage = feature_lineage_document(
        raw_s3_uri=config.raw_data_s3_uri,
        cleaned_s3_uri=config.cleaned_data_s3_uri,
        curated_s3_uri=config.curated_features_s3_uri,
        feature_group_name=config.feature_group_name,
        transformations=[*cleaning_steps, *curation_steps],
        row_counts={
            "raw": int(len(raw)),
            "cleaned": int(len(cleaned)),
            "curated": int(len(curated)),
        },
        producer="src.prepare_feature_sources",
    )
    config.feature_lineage_local_path.write_text(
        json.dumps(lineage, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    put_json_s3(config, lineage, config.feature_lineage_s3_uri)

    update_state(
        cleaned_data_s3_uri=config.cleaned_data_s3_uri,
        curated_features_s3_uri=config.curated_features_s3_uri,
        feature_snapshot_s3_uri=config.feature_snapshot_s3_uri,
        feature_lineage_s3_uri=config.feature_lineage_s3_uri,
        feature_lineage_local_path=str(config.feature_lineage_local_path),
        cleaned_rows=int(len(cleaned)),
        curated_rows=int(len(curated)),
    )
    LOGGER.info("Prepared cleaned data at %s and %s", config.cleaned_data_local_path, config.cleaned_data_s3_uri)
    LOGGER.info("Prepared curated features at %s and %s", config.curated_features_local_path, config.curated_features_s3_uri)
    LOGGER.info("Feature lineage written to %s and %s", config.feature_lineage_local_path, config.feature_lineage_s3_uri)


if __name__ == "__main__":
    main()
