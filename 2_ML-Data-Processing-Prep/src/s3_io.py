"""S3 IO helpers used by Glue and local AWS scripts."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.data_utils import json_safe


def read_csv_from_s3(s3_client: Any, bucket_name: str, key: str) -> pd.DataFrame:
    response = s3_client.get_object(Bucket=bucket_name, Key=key)
    body = response["Body"].read()
    return pd.read_csv(io.BytesIO(body))


def write_csv_to_s3(s3_client: Any, df: pd.DataFrame, bucket_name: str, key: str) -> None:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    s3_client.put_object(Bucket=bucket_name, Key=key, Body=buffer.getvalue().encode("utf-8"))


def write_json_to_s3(s3_client: Any, payload: dict[str, Any], bucket_name: str, key: str) -> None:
    body = json.dumps(json_safe(payload), indent=2, sort_keys=True).encode("utf-8")
    s3_client.put_object(Bucket=bucket_name, Key=key, Body=body, ContentType="application/json")


def write_text_to_s3(s3_client: Any, text: str, bucket_name: str, key: str, content_type: str = "text/plain") -> None:
    s3_client.put_object(Bucket=bucket_name, Key=key, Body=text.encode("utf-8"), ContentType=content_type)


def upload_file(s3_client: Any, local_path: Path, bucket_name: str, key: str) -> None:
    s3_client.upload_file(str(local_path), bucket_name, key)


def ensure_prefixes(s3_client: Any, bucket_name: str, prefixes: list[str]) -> None:
    for prefix in prefixes:
        key = f"{prefix.strip('/')}/.keep"
        s3_client.put_object(Bucket=bucket_name, Key=key, Body=b"")


def download_prefix(s3_client: Any, bucket_name: str, prefix: str, output_dir: Path) -> int:
    paginator = s3_client.get_paginator("list_objects_v2")
    count = 0
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            if key.endswith("/.keep"):
                continue
            target = output_dir / key
            target.parent.mkdir(parents=True, exist_ok=True)
            s3_client.download_file(bucket_name, key, str(target))
            count += 1
    return count

