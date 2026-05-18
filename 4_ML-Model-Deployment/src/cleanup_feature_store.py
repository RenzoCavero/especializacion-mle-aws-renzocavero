from __future__ import annotations

import argparse
import time
from typing import Any

from .aws_clients import client_error_code, clients
from .cleanup_batch_resources import _delete_s3_prefix, is_lab_s3_uri
from .config import load_config, parse_s3_uri, read_json, utc_now, write_json


def _feature_group_exists(sagemaker: Any, feature_group_name: str) -> bool:
    try:
        sagemaker.describe_feature_group(FeatureGroupName=feature_group_name)
        return True
    except Exception as exc:
        return client_error_code(exc) not in {"ResourceNotFound", "ValidationException"}


def cleanup_feature_store(delete_s3: bool = False, wait: bool = True) -> dict[str, Any]:
    config = load_config(require_aws=True)
    metadata = read_json(config.metadata_path("feature_store.json"), default={})
    feature_group_name = metadata.get("feature_group_name") or config.feature_group_name
    created_by_lab = bool(metadata.get("created_by_lab"))
    actions: list[str] = []
    deleted_s3_objects = 0

    aws = clients(config)
    sagemaker = aws.sagemaker

    if feature_group_name and created_by_lab and _feature_group_exists(sagemaker, feature_group_name):
        try:
            sagemaker.delete_feature_group(FeatureGroupName=feature_group_name)
            actions.append(f"delete_feature_group:{feature_group_name}")
            if wait:
                for _ in range(60):
                    if not _feature_group_exists(sagemaker, feature_group_name):
                        break
                    time.sleep(10)
        except Exception as exc:
            if client_error_code(exc) not in {"ResourceNotFound", "ValidationException"}:
                raise
    elif feature_group_name:
        actions.append(f"preserve_external_feature_group:{feature_group_name}")

    if delete_s3 or config.delete_lab_s3:
        for uri in (
            metadata.get("offline_export_s3_uri"),
            metadata.get("offline_store_s3_uri"),
        ):
            if uri and is_lab_s3_uri(config, uri):
                bucket, key = parse_s3_uri(uri)
                deleted_s3_objects += _delete_s3_prefix(aws.s3, bucket, key)
                actions.append(f"delete_s3_prefix:{uri}")

    output = {
        "actions": actions,
        "deleted_s3_objects": deleted_s3_objects,
        "delete_s3_requested": bool(delete_s3 or config.delete_lab_s3),
        "external_feature_groups_preserved": not created_by_lab,
        "completed_at": utc_now(),
    }
    write_json(config.metadata_path("cleanup_feature_store.json"), output)
    print("Cleanup Feature Store completado.")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup seguro de Feature Store del laboratorio.")
    parser.add_argument("--delete-s3", action="store_true", help="Borrar prefijos S3 del Feature Store del lab.")
    parser.add_argument("--no-wait", action="store_true", help="No esperar borrado del Feature Group.")
    args = parser.parse_args()
    cleanup_feature_store(delete_s3=args.delete_s3, wait=not args.no_wait)


if __name__ == "__main__":
    main()
