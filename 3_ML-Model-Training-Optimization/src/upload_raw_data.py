from __future__ import annotations

import logging

from src.aws_clients import upload_file
from src.config import get_config
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

    upload_file(config, str(config.raw_data_local_path), config.raw_data_s3_uri)
    upload_file(config, str(config.raw_data_local_path), config.feature_snapshot_s3_uri)
    update_state(
        raw_data_s3_uri=config.raw_data_s3_uri,
        feature_snapshot_s3_uri=config.feature_snapshot_s3_uri,
    )
    LOGGER.info("Uploaded raw data to %s", config.raw_data_s3_uri)
    LOGGER.info("Uploaded processing feature snapshot to %s", config.feature_snapshot_s3_uri)


if __name__ == "__main__":
    main()
