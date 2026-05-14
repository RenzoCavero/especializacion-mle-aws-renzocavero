from __future__ import annotations

import logging
from pathlib import Path

from src.aws_clients import client
from src.config import get_config
from src.logging_utils import configure_logging


LOGGER = logging.getLogger(__name__)


PREFIXES = ("reports/", "evaluation/", "metrics/", "model_registry_metadata/")


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    s3 = client(config, "s3")
    destination_root = config.local_outputs_dir / "downloaded_s3_outputs"
    destination_root.mkdir(parents=True, exist_ok=True)

    for prefix in PREFIXES:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=config.s3_bucket_name, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item["Key"]
                if key.endswith("/"):
                    continue
                local_path = destination_root / key
                local_path.parent.mkdir(parents=True, exist_ok=True)
                s3.download_file(config.s3_bucket_name, key, str(local_path))
                LOGGER.info("Downloaded s3://%s/%s to %s", config.s3_bucket_name, key, local_path)


if __name__ == "__main__":
    main()
