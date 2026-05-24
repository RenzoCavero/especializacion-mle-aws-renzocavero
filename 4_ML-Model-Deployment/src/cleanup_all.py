from __future__ import annotations

import argparse

from .cleanup_batch_resources import cleanup_batch_resources
from .cleanup_endpoint_resources import cleanup_endpoint_resources
from .cleanup_feature_store import cleanup_feature_store
from .config import load_config, utc_now, write_json


def cleanup_all(delete_s3: bool = False, no_wait: bool = False) -> dict[str, object]:
    config = load_config(require_aws=True)
    endpoint = cleanup_endpoint_resources(wait=not no_wait)
    batch = cleanup_batch_resources(delete_s3=delete_s3)
    feature_store = cleanup_feature_store(delete_s3=delete_s3, wait=not no_wait)
    metadata = {
        "endpoint_cleanup": endpoint,
        "batch_cleanup": batch,
        "feature_store_cleanup": feature_store,
        "s3_outputs_deleted": bool(delete_s3),
        "external_resources_preserved": [
            "Model Package",
            "Feature Group not created by Lab 04",
            "Offline Store not created by Lab 04",
            "Online Store not created by Lab 04",
        ],
        "completed_at": utc_now(),
    }
    write_json(config.metadata_path("cleanup_all.json"), metadata)
    print("Cleanup all completado. Recursos externos conservados por defecto.")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup seguro completo del laboratorio 4.")
    parser.add_argument(
        "--delete-s3",
        action="store_true",
        help="Borrar tambien prefijos S3 del laboratorio. Por defecto se conservan.",
    )
    parser.add_argument("--no-wait", action="store_true", help="No esperar borrado del endpoint.")
    args = parser.parse_args()
    cleanup_all(delete_s3=args.delete_s3, no_wait=args.no_wait)


if __name__ == "__main__":
    main()
