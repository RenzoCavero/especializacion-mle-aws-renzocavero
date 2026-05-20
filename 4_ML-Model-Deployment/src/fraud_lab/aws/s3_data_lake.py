from __future__ import annotations

import csv
import io
import json
from typing import Any, Iterable

from src.aws_clients import client_error_code

from fraud_lab.aws.clients import FraudAwsClients
from fraud_lab.aws.config import FraudAwsConfig, load_fraud_aws_config


class S3DataLake:
    """Capa delgada para escribir y leer objetos del data lake en S3."""

    def __init__(
        self,
        config: FraudAwsConfig | None = None,
        clients: FraudAwsClients | None = None,
    ) -> None:
        self.config = config or load_fraud_aws_config()
        self.clients = clients or FraudAwsClients(self.config)
        self.s3 = self.clients.s3

    def uri(self, *parts: str) -> str:
        return self.config.s3_uri(*parts)

    def put_text(self, parts: tuple[str, ...], text: str, content_type: str) -> str:
        key = self.config.s3_key(*parts)
        self.s3.put_object(
            Bucket=self.config.s3_bucket_name,
            Key=key,
            Body=text.encode("utf-8"),
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )
        return f"s3://{self.config.s3_bucket_name}/{key}"

    def read_text(self, *parts: str) -> str:
        key = self.config.s3_key(*parts)
        try:
            response = self.s3.get_object(Bucket=self.config.s3_bucket_name, Key=key)
        except Exception as exc:
            if client_error_code(exc) in {"NoSuchKey", "404"}:
                return ""
            raise
        return response["Body"].read().decode("utf-8")

    def put_json(self, parts: tuple[str, ...], payload: dict[str, Any]) -> str:
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        return self.put_text(parts, text, "application/json")

    def read_json(self, *parts: str) -> dict[str, Any]:
        text = self.read_text(*parts)
        if not text:
            return {}
        return json.loads(text)

    def put_jsonl(self, parts: tuple[str, ...], rows: Iterable[dict[str, Any]]) -> str:
        text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
        return self.put_text(parts, text, "application/jsonlines")

    def read_jsonl(self, *parts: str) -> list[dict[str, Any]]:
        text = self.read_text(*parts)
        rows: list[dict[str, Any]] = []
        for line in text.splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def put_csv(
        self,
        parts: tuple[str, ...],
        rows: list[dict[str, Any]],
        fieldnames: list[str] | None = None,
    ) -> str:
        output = io.StringIO()
        if rows or fieldnames:
            fields = fieldnames or list(rows[0].keys())
            writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return self.put_text(parts, output.getvalue(), "text/csv")

    def read_csv(self, *parts: str) -> list[dict[str, str]]:
        text = self.read_text(*parts)
        if not text.strip():
            return []
        return list(csv.DictReader(io.StringIO(text)))

