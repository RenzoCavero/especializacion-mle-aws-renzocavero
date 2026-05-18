from __future__ import annotations

import argparse

from .config import load_config, read_json, utc_now


def _value(data: dict, key: str, default: str = "") -> str:
    value = data.get(key, default)
    return str(value) if value is not None else default


def generate_deployment_report() -> dict[str, str]:
    config = load_config(require_aws=False)
    model = read_json(config.metadata_path("model_resolution.json"), default={})
    sm_model = read_json(config.metadata_path("sagemaker_model.json"), default={})
    batch = read_json(config.metadata_path("batch_transform_job.json"), default={})
    endpoint_config = read_json(config.metadata_path("endpoint_config.json"), default={})
    endpoint = read_json(config.metadata_path("realtime_endpoint.json"), default={})
    feature_store = read_json(config.metadata_path("feature_store.json"), default={})
    autoscaling = read_json(config.metadata_path("autoscaling.json"), default={})
    metrics = read_json(config.metadata_path("cloudwatch_metrics.json"), default={})

    lines = [
        "# Deployment report - Laboratorio 4",
        "",
        f"- Generated at: {utc_now()}",
        f"- LAB_MODE: `{config.lab_mode}`",
        f"- AWS region: `{config.aws_region}`",
        "",
        "## Modelo",
        "",
        f"- SageMaker Model: `{_value(sm_model, 'model_name', config.model_name)}`",
        f"- Model artifact: `{_value(model, 'model_artifact_s3_uri')}`",
        f"- Model package: `{_value(model, 'model_package_arn', 'N/A')}`",
        "",
        "## Patron batch",
        "",
        "- Servicio: SageMaker Batch Transform Job",
        f"- Batch input S3: `{_value(batch, 'batch_input_s3_uri')}`",
        f"- Batch output S3: `{_value(batch, 'batch_output_s3_uri')}`",
        f"- Transform job: `{_value(batch, 'transform_job_name')}`",
        "",
        "## Patron real-time",
        "",
        "- Servicio: SageMaker Real-Time Endpoint",
        f"- Endpoint config: `{_value(endpoint_config, 'endpoint_config_name')}`",
        f"- Endpoint name: `{_value(endpoint, 'endpoint_name', config.endpoint_name)}`",
        f"- Endpoint status: `{_value(endpoint, 'endpoint_status')}`",
        "",
        "## Feature Store",
        "",
        f"- Feature Group: `{_value(feature_store, 'feature_group_name', config.feature_group_name or 'N/A')}`",
        f"- Online Store: `{'enabled' if feature_store.get('online_store_enabled', config.feature_group_name) else 'disabled'}`",
        f"- Offline Store S3: `{_value(feature_store, 'offline_store_s3_uri', config.offline_store_s3_uri or 'N/A')}`",
        f"- Offline export for batch: `{_value(feature_store, 'offline_export_s3_uri', 'N/A')}`",
        f"- Transformation script: `{_value(feature_store, 'transformation_script', 'src/feature_transformations.py')}`",
        "",
        "## Data capture y autoscaling",
        "",
        f"- Data capture: `{_value(endpoint_config, 'data_capture_s3_uri', 'disabled')}`",
        f"- Autoscaling: `{autoscaling.get('enabled', False)}`",
        f"- Autoscaling config: `{autoscaling}`",
        "",
        "## Metricas",
        "",
        f"- CloudWatch metrics checked: `{bool(metrics.get('metrics'))}`",
        f"- Metrics file: `artifacts/local_outputs/cloudwatch_metrics.json`",
        "",
        "## Cost warnings",
        "",
        "- SageMaker Real-Time Endpoint genera costo mientras este activo.",
        "- Batch Transform genera costo durante la ejecucion del job.",
        "- Feature Store Online/Offline Store y S3 pueden generar costos.",
        "",
        "## Cleanup steps",
        "",
        "```bash",
        "make destroy-endpoint",
        "make destroy-all",
        "```",
        "",
        "## Preparacion para monitoreo y drift",
        "",
        "El laboratorio deja data capture, outputs batch, request_id, model_version, metricas y logs para el laboratorio 6.",
    ]
    report_path = config.metadata_path("deployment_report.md")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Deployment report: {report_path}")
    return {"deployment_report": str(report_path)}


def main() -> None:
    argparse.ArgumentParser(description="Generar reporte de despliegue.").parse_args()
    generate_deployment_report()


if __name__ == "__main__":
    main()
