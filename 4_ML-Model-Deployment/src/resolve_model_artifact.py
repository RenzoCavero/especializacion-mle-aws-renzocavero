from __future__ import annotations

import argparse
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from .aws_clients import client_error_code, clients, get_sklearn_image_uri
from .config import (
    ConfigError,
    FeatureContract,
    LOCAL_CACHE_DIR,
    ROOT_DIR,
    load_config,
    save_feature_contract,
    timestamp_slug,
    utc_now,
    write_json,
)


def _copy_inference_code(target_dir: Path) -> None:
    code_dir = target_dir / "code"
    code_dir.mkdir(parents=True, exist_ok=True)
    source_dir = Path(__file__).resolve().parents[1] / "inference"
    for file_name in (
        "inference.py",
        "model_fn.py",
        "input_fn.py",
        "predict_fn.py",
        "output_fn.py",
        "requirements.txt",
    ):
        shutil.copy2(source_dir / file_name, code_dir / file_name)


def create_standalone_model_artifact() -> Path:
    try:
        import joblib
        from sklearn.linear_model import LogisticRegression
    except ImportError as exc:
        raise ConfigError(
            "standalone_mode requiere scikit-learn y joblib. "
            "Ejecuta: pip install -r requirements.txt"
        ) from exc

    contract = FeatureContract.standalone()
    save_feature_contract(contract)
    model_dir = LOCAL_CACHE_DIR / "standalone_model"
    if model_dir.exists():
        shutil.rmtree(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    labels = []
    for idx in range(120):
        age = 22 + (idx % 45)
        income = 28000 + (idx * 1370) % 90000
        tenure = 1 + (idx * 3) % 72
        spend = 30 + (idx * 17) % 420
        tickets = idx % 6
        score = (
            0.02 * (age - 35)
            - 0.00001 * (income - 50000)
            - 0.015 * tenure
            + 0.002 * spend
            + 0.18 * tickets
        )
        label = int(score > 0.25)
        rows.append([age, income, tenure, spend, tickets])
        labels.append(label)

    model = LogisticRegression(max_iter=300)
    model.fit(pd.DataFrame(rows, columns=contract.inference_features), labels)
    joblib.dump(model, model_dir / "model.joblib")
    _copy_inference_code(model_dir)

    artifact_path = LOCAL_CACHE_DIR / "model.tar.gz"
    with tarfile.open(artifact_path, "w:gz") as tar:
        tar.add(model_dir / "model.joblib", arcname="model.joblib")
        tar.add(model_dir / "code", arcname="code")
    return artifact_path


def _container_from_model_package(description: dict[str, Any]) -> dict[str, str]:
    containers = description.get("InferenceSpecification", {}).get("Containers", [])
    if not containers:
        raise ConfigError("El Model Package no contiene InferenceSpecification.Containers.")
    container = containers[0]
    model_data = container.get("ModelDataUrl") or container.get("ModelDataSource", {}).get(
        "S3DataSource", {}
    ).get("S3Uri")
    image = container.get("Image")
    if not model_data or not image:
        raise ConfigError("El Model Package no expone ModelDataUrl/Image utilizables.")
    return {"model_artifact_s3_uri": model_data, "image_uri": image}


def _latest_model_package_arn(sagemaker: Any, group_name: str) -> str:
    for approved_only in (True, False):
        params: dict[str, Any] = {
            "ModelPackageGroupName": group_name,
            "SortBy": "CreationTime",
            "SortOrder": "Descending",
            "MaxResults": 10,
        }
        if approved_only:
            params["ModelApprovalStatus"] = "Approved"
        response = sagemaker.list_model_packages(**params)
        packages = response.get("ModelPackageSummaryList", [])
        if packages:
            return packages[0]["ModelPackageArn"]
    raise ConfigError(
        f"No se encontraron Model Packages en MODEL_PACKAGE_GROUP_NAME={group_name!r}."
    )


def resolve_model_artifact() -> dict[str, Any]:
    config = load_config(require_aws=True)
    aws = clients(config)
    sagemaker = aws.sagemaker
    s3 = aws.s3

    if config.lab_mode == "integrated":
        model_package_arn = config.model_package_arn
        source = "model_package_arn"
        if not model_package_arn and config.model_package_group_name:
            model_package_arn = _latest_model_package_arn(sagemaker, config.model_package_group_name)
            source = "model_package_group_latest"

        if model_package_arn:
            description = sagemaker.describe_model_package(ModelPackageName=model_package_arn)
            container = _container_from_model_package(description)
            metadata = {
                **container,
                "source": source,
                "model_package_arn": model_package_arn,
                "model_package_group_name": config.model_package_group_name,
                "lab_mode": config.lab_mode,
                "resolved_at": utc_now(),
                "external_artifact": True,
            }
        elif config.model_artifact_s3_uri:
            metadata = {
                "model_artifact_s3_uri": config.model_artifact_s3_uri,
                "image_uri": get_sklearn_image_uri(config),
                "source": "MODEL_ARTIFACT_S3_URI",
                "model_package_arn": "",
                "model_package_group_name": config.model_package_group_name,
                "lab_mode": config.lab_mode,
                "resolved_at": utc_now(),
                "external_artifact": True,
            }
        else:
            raise ConfigError("No se pudo resolver un artefacto de modelo para integrated_mode.")
    else:
        if not config.create_standalone_model:
            raise ConfigError("CREATE_STANDALONE_MODEL=false, pero standalone_mode necesita un modelo.")
        artifact_path = create_standalone_model_artifact()
        bucket_key = "/".join(
            [
                config.s3_prefix.strip("/"),
                "artifacts",
                "standalone",
                timestamp_slug(),
                "model.tar.gz",
            ]
        )
        s3.upload_file(str(artifact_path), config.s3_bucket_name, bucket_key)
        metadata = {
            "model_artifact_s3_uri": f"s3://{config.s3_bucket_name}/{bucket_key}",
            "image_uri": get_sklearn_image_uri(config),
            "source": "standalone_generated_model",
            "model_package_arn": "",
            "model_package_group_name": "",
            "lab_mode": config.lab_mode,
            "resolved_at": utc_now(),
            "local_artifact_path": str(artifact_path.relative_to(ROOT_DIR)),
            "external_artifact": False,
        }

    output_path = config.metadata_path("model_resolution.json")
    write_json(output_path, metadata)
    print(f"Modelo resuelto: {metadata['model_artifact_s3_uri']}")
    print(f"Metadata: {output_path}")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolver artefacto model.tar.gz para el laboratorio 4.")
    parser.parse_args()
    try:
        resolve_model_artifact()
    except Exception as exc:
        if client_error_code(exc) in {"AccessDenied", "AccessDeniedException"}:
            raise SystemExit("Permisos insuficientes para resolver el modelo. Revisa IAM.") from exc
        raise


if __name__ == "__main__":
    main()
