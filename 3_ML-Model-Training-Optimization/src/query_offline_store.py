from __future__ import annotations

import logging

from src.aws_clients import list_s3_keys
from src.config import get_config
from src.logging_utils import configure_logging
from src.state import update_state


LOGGER = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()

    keys = list_s3_keys(config, config.offline_store_s3_uri, max_keys=20)
    output_path = config.local_outputs_dir / "offline_store_validation.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if keys:
        message = (
            "Offline Store has written objects to S3.\n"
            f"Prefix: {config.offline_store_s3_uri}\n"
            + "\n".join(keys)
        )
        LOGGER.info("Offline Store validation found %s object(s)", len(keys))
    else:
        message = (
            "No Offline Store objects were visible yet. This can happen because Feature Store writes "
            "to Offline Store asynchronously. The Processing Job uses the uploaded feature snapshot "
            f"at {config.feature_snapshot_s3_uri}, which is produced from the same validated feature records. "
            "Re-run this command after a few minutes to confirm Offline Store materialization."
        )
        LOGGER.warning(message)

    output_path.write_text(message, encoding="utf-8")
    update_state(
        offline_store_s3_uri=config.offline_store_s3_uri,
        offline_store_visible_keys=keys,
        offline_store_validation_path=str(output_path),
    )
    print(message)


if __name__ == "__main__":
    main()
