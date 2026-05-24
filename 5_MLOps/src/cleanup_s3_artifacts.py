"""Delete S3 artifacts created under the lab-owned prefix."""

from __future__ import annotations

import argparse
import json
from typing import Any

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    class ClientError(Exception):
        response = {"Error": {"Code": "Unknown"}}

from .aws_clients import create_clients
from .config import load_config, write_metadata


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    bucket_key = uri[5:]
    bucket, _, key = bucket_key.partition("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI without bucket/key: {uri}")
    return bucket, key.rstrip("/")


def _lab_prefix(config) -> tuple[str, str]:
    bucket, prefix = _parse_s3_uri(config.s3_base_uri)
    expected_prefix = f"{config.resource_prefix}/{config.environment}".strip("/")
    if bucket != config.s3_bucket_name:
        raise ValueError("Refusing to delete S3 artifacts because s3_base_uri bucket does not match S3_BUCKET_NAME.")
    if prefix != expected_prefix:
        raise ValueError(
            f"Refusing to delete unexpected S3 prefix {prefix!r}; expected the lab prefix {expected_prefix!r}."
        )
    if not prefix or prefix in {".", "/"} or len(prefix.split("/")) < 2:
        raise ValueError(f"Refusing to delete broad S3 prefix: {prefix!r}")
    return bucket, f"{prefix}/"


def _delete_objects(s3, *, bucket: str, objects: list[dict[str, str]]) -> int:
    deleted = 0
    for index in range(0, len(objects), 1000):
        batch = objects[index : index + 1000]
        if not batch:
            continue
        s3.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})
        deleted += len(batch)
    return deleted


def cleanup_s3_artifacts(*, execute: bool = True) -> dict[str, object]:
    config = load_config(validate=True)
    if not config.s3_base_uri:
        payload = {"skipped": True, "reason": "S3_BUCKET_NAME is not configured"}
        write_metadata(config, "cleanup_s3_artifacts", payload)
        return payload

    clients = create_clients(config)
    bucket, prefix = _lab_prefix(config)
    object_keys: list[dict[str, str]] = []
    version_keys: list[dict[str, str]] = []
    delete_marker_keys: list[dict[str, str]] = []

    paginator = clients.s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = str(item.get("Key") or "")
            if key:
                object_keys.append({"Key": key})

    try:
        version_paginator = clients.s3.get_paginator("list_object_versions")
        for page in version_paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Versions", []):
                key = str(item.get("Key") or "")
                version_id = str(item.get("VersionId") or "")
                if key and version_id:
                    version_keys.append({"Key": key, "VersionId": version_id})
            for item in page.get("DeleteMarkers", []):
                key = str(item.get("Key") or "")
                version_id = str(item.get("VersionId") or "")
                if key and version_id:
                    delete_marker_keys.append({"Key": key, "VersionId": version_id})
    except ClientError as exc:
        version_listing_error: str | None = exc.response.get("Error", {}).get("Code", "")
    except Exception as exc:  # pragma: no cover - some fake clients do not implement version listing
        version_listing_error = exc.__class__.__name__
    else:
        version_listing_error = None

    if execute:
        deleted_objects = _delete_objects(clients.s3, bucket=bucket, objects=object_keys)
        deleted_versions = _delete_objects(clients.s3, bucket=bucket, objects=version_keys)
        deleted_markers = _delete_objects(clients.s3, bucket=bucket, objects=delete_marker_keys)
    else:
        deleted_objects = 0
        deleted_versions = 0
        deleted_markers = 0

    payload: dict[str, Any] = {
        "bucket": bucket,
        "prefix": prefix,
        "s3_uri": f"s3://{bucket}/{prefix}",
        "execute": execute,
        "objects_found": len(object_keys),
        "versions_found": len(version_keys),
        "delete_markers_found": len(delete_marker_keys),
        "objects_deleted": deleted_objects,
        "versions_deleted": deleted_versions,
        "delete_markers_deleted": deleted_markers,
        "version_listing_error": version_listing_error or "",
        "safety_note": "Only objects under the exact lab prefix RESOURCE_PREFIX/ENVIRONMENT are eligible for deletion.",
    }
    write_metadata(config, "cleanup_s3_artifacts", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(cleanup_s3_artifacts(execute=not args.plan_only), indent=2, default=str))


if __name__ == "__main__":
    main()
