from __future__ import annotations

import argparse
from pathlib import Path

from .aws_clients import client_error_code, clients
from .config import ConfigError, load_config, parse_s3_uri, read_json, utc_now, write_json


def collect_batch_output() -> dict[str, object]:
    config = load_config(require_aws=True)
    job_metadata = read_json(config.metadata_path("batch_transform_job.json"))
    output_s3_uri = job_metadata["batch_output_s3_uri"]
    bucket, prefix = parse_s3_uri(output_s3_uri)
    local_dir = config.metadata_path("batch")
    local_dir.mkdir(parents=True, exist_ok=True)

    s3 = clients(config).s3
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix.rstrip("/") + "/")
    objects = [item for item in response.get("Contents", []) if not item["Key"].endswith("/")]
    if not objects:
        raise ConfigError(
            f"No se encontraron predicciones en {output_s3_uri}. "
            "Revisa el estado del Batch Transform Job y CloudWatch Logs."
        )

    downloaded: list[str] = []
    for item in objects:
        local_path = local_dir / Path(item["Key"]).name
        s3.download_file(bucket, item["Key"], str(local_path))
        if local_path.stat().st_size > 0:
            downloaded.append(str(local_path))
    if not downloaded:
        raise ConfigError("Los archivos descargados de batch output estan vacios.")

    metadata = {
        "batch_output_s3_uri": output_s3_uri,
        "downloaded_files": downloaded,
        "downloaded_count": len(downloaded),
        "collected_at": utc_now(),
    }
    write_json(config.metadata_path("batch_output_collection.json"), metadata)
    print(f"Batch outputs descargados: {len(downloaded)}")
    return metadata


def main() -> None:
    argparse.ArgumentParser(description="Descargar outputs de Batch Transform desde S3.").parse_args()
    try:
        collect_batch_output()
    except Exception as exc:
        if client_error_code(exc) in {"AccessDenied", "AccessDeniedException"}:
            raise SystemExit("Permisos insuficientes para descargar batch outputs.") from exc
        raise


if __name__ == "__main__":
    main()
