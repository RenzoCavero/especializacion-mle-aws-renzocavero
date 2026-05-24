from __future__ import annotations

import argparse

from .config import load_config, read_json, utc_now, write_json


def configure_or_document_data_capture() -> dict[str, object]:
    config = load_config(require_aws=False)
    endpoint_config = read_json(config.metadata_path("endpoint_config.json"), default={})
    metadata = {
        "data_capture_enabled": bool(endpoint_config.get("data_capture_enabled", config.enable_data_capture)),
        "data_capture_s3_uri": endpoint_config.get("data_capture_s3_uri", config.data_capture_s3_uri),
        "configured_from": "create_endpoint_config.py",
        "note": (
            "SageMaker Endpoint Data Capture se define al crear Endpoint Configuration. "
            "Si necesitas cambiarlo, crea un nuevo endpoint config y actualiza el endpoint."
        ),
        "prepared_for_lab_06_monitoring": True,
        "updated_at": utc_now(),
    }
    write_json(config.metadata_path("data_capture.json"), metadata)
    print(f"Data capture location: {metadata['data_capture_s3_uri']}")
    return metadata


def main() -> None:
    argparse.ArgumentParser(description="Documentar configuracion de data capture.").parse_args()
    configure_or_document_data_capture()


if __name__ == "__main__":
    main()
