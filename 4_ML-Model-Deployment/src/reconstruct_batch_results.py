from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .aws_clients import client_error_code, clients
from .config import ConfigError, ROOT_DIR, load_config, read_json, utc_now, write_json
from .validate_request_response import normalize_response


def _parse_prediction_line(line: str) -> dict[str, Any]:
    line = line.strip()
    if not line:
        return {"score": 0.0}
    try:
        raw = json.loads(line)
        return normalize_response(raw)
    except Exception:
        first_value = line.split(",")[0]
        return normalize_response(float(first_value))


def _load_predictions(files: list[str]) -> list[dict[str, Any]]:
    predictions: list[dict[str, Any]] = []
    for file_name in files:
        for line in Path(file_name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                predictions.append(_parse_prediction_line(line))
    return predictions


def reconstruct_batch_results(upload_report: bool = True) -> dict[str, object]:
    config = load_config(require_aws=False)
    input_metadata = read_json(config.metadata_path("batch_input.json"))
    job_metadata = read_json(config.metadata_path("batch_transform_job.json"))
    collection = read_json(config.metadata_path("batch_output_collection.json"))

    manifest = pd.read_csv(ROOT_DIR / input_metadata["local_manifest"])
    predictions = _load_predictions(collection["downloaded_files"])
    if len(predictions) < len(manifest):
        raise ConfigError(
            "Hay menos predicciones que registros de entrada. "
            "Revisa errores del contenedor o el formato del Batch Transform Job."
        )

    result = manifest.copy()
    result["score"] = [predictions[idx]["score"] for idx in range(len(result))]
    result["predicted_label"] = [
        predictions[idx]["predicted_label"] for idx in range(len(result))
    ]
    result["decision"] = [predictions[idx]["decision"] for idx in range(len(result))]
    result["model_name"] = job_metadata["model_name"]
    result["transform_job_name"] = job_metadata["transform_job_name"]
    result["timestamp"] = utc_now()
    result["output_s3_uri"] = job_metadata["batch_output_s3_uri"]

    csv_path = config.metadata_path("batch_predictions_reconstructed.csv")
    report_path = config.metadata_path("batch_predictions_report.md")
    result.to_csv(csv_path, index=False)
    report = [
        "# Batch predictions report",
        "",
        f"- Transform job: `{job_metadata['transform_job_name']}`",
        f"- Model: `{job_metadata['model_name']}`",
        f"- Output S3: `{job_metadata['batch_output_s3_uri']}`",
        f"- Records: {len(result)}",
        f"- Generated at: {utc_now()}",
        "",
        "El archivo CSV reconstruido conserva el identificador original y agrega score, etiqueta y decision.",
    ]
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    uploaded: list[str] = []
    if upload_report:
        try:
            aws_config = load_config(require_aws=True)
            s3 = clients(aws_config).s3
            for local_path in (csv_path, report_path):
                key = "/".join(
                    [
                        aws_config.s3_prefix.strip("/"),
                        "reports",
                        job_metadata["transform_job_name"],
                        local_path.name,
                    ]
                )
                s3.upload_file(str(local_path), aws_config.s3_bucket_name, key)
                uploaded.append(f"s3://{aws_config.s3_bucket_name}/{key}")
        except Exception:
            uploaded = []

    metadata = {
        "reconstructed_csv": str(csv_path),
        "report": str(report_path),
        "records": len(result),
        "uploaded_reports": uploaded,
        "created_at": utc_now(),
    }
    write_json(config.metadata_path("batch_reconstruction.json"), metadata)
    print(f"Resultados batch reconstruidos: {csv_path}")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstruir resultados batch con IDs originales.")
    parser.add_argument("--no-upload", action="store_true", help="No subir reporte a S3.")
    args = parser.parse_args()
    try:
        reconstruct_batch_results(upload_report=not args.no_upload)
    except Exception as exc:
        if client_error_code(exc) in {"AccessDenied", "AccessDeniedException"}:
            raise SystemExit("Permisos insuficientes para subir reporte batch a S3.") from exc
        raise


if __name__ == "__main__":
    main()
