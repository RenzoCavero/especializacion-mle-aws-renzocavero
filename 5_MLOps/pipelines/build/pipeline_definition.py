"""SageMaker build pipeline definition.

The pure contract functions are used by unit tests. The SageMaker SDK function
is imported lazily so tests do not need AWS or SageMaker network access.
"""

from __future__ import annotations

import json
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from src.aws_clients import create_clients
from src.compute import resolve_pipeline_compute
from src.config import LabConfig, write_metadata
from .parameters import FRAMEWORK_VERSION, PIPELINE_STEPS, PYTHON_VERSION

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - keeps local contract tests dependency-light
    class ClientError(Exception):
        response = {"Error": {"Code": "Unknown"}}


def build_pipeline_contract(config: LabConfig) -> dict[str, Any]:
    return {
        "name": config.pipeline_name,
        "mode": config.lab_mode,
        "steps": PIPELINE_STEPS,
        "quality_gate": {
            "metric_rules": [
                {"name": "f1", "operator": ">=", "threshold": config.f1_threshold},
                {"name": "auc", "operator": ">=", "threshold": config.auc_threshold},
            ]
        },
        "registry": {
            "model_package_group_name": config.model_package_group_name,
            "initial_approval_status": "PendingManualApproval",
        },
        "inputs": {
            "raw_data": f"{config.raw_data_s3_uri}/churn_train.csv",
            "train_data": config.train_data_s3_uri,
            "test_data": config.test_data_s3_uri,
        },
        "outputs": {
            "evaluation": config.evaluation_s3_uri,
            "model_artifacts": config.model_artifacts_s3_uri,
        },
    }


def save_pipeline_contract(config: LabConfig) -> Path:
    payload = build_pipeline_contract(config)
    path = config.local_outputs_dir / "pipeline_contract.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_metadata(config, "pipeline_definition", payload)
    return path


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    bucket_key = uri[5:]
    bucket, _, key = bucket_key.partition("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI without bucket/key: {uri}")
    return bucket, key


def _upload_file(s3_client: Any, source: Path, destination_s3_uri: str) -> str:
    bucket, key = _parse_s3_uri(destination_s3_uri)
    s3_client.upload_file(str(source), bucket, key)
    return destination_s3_uri


def _upload_training_source(s3_client: Any, config: LabConfig) -> str:
    source_dir = Path("training")
    destination = f"{config.artifacts_s3_uri}/source/training.tar.gz"
    bucket, key = _parse_s3_uri(destination)
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = Path(temp_dir) / "training.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            for path in source_dir.rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    archive.add(path, arcname=path.relative_to(source_dir))
        s3_client.upload_file(str(archive_path), bucket, key)
    return destination


def _sklearn_image_uri(config: LabConfig) -> str:
    if config.model_image_uri:
        return config.model_image_uri
    framework_accounts = {
        "af-south-1": "626614931356",
        "ap-east-1": "871362719292",
        "ap-northeast-1": "354813040037",
        "ap-northeast-2": "366743142698",
        "ap-south-1": "720646828776",
        "ap-southeast-1": "121021644041",
        "ap-southeast-2": "783357654285",
        "ca-central-1": "341280168497",
        "eu-central-1": "492215442770",
        "eu-north-1": "662702820516",
        "eu-south-1": "692866216735",
        "eu-west-1": "141502667606",
        "eu-west-2": "764974769150",
        "eu-west-3": "659782779980",
        "me-south-1": "217643126080",
        "sa-east-1": "737474898029",
        "us-east-1": "683313688378",
        "us-east-2": "257758044811",
        "us-west-1": "746614075791",
        "us-west-2": "246618743249",
    }
    account_id = framework_accounts.get(config.aws_region)
    if not account_id:
        raise ValueError(
            "Could not resolve the SageMaker scikit-learn image for this region. "
            "Set MODEL_IMAGE_URI in .env."
        )
    return f"{account_id}.dkr.ecr.{config.aws_region}.amazonaws.com/sagemaker-scikit-learn:{FRAMEWORK_VERSION}-cpu-{PYTHON_VERSION}"


def _processing_step(
    *,
    name: str,
    role: str,
    image_uri: str,
    instance_type: str,
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    entrypoint: str,
    arguments: list[Any],
) -> dict[str, Any]:
    return {
        "Name": name,
        "Type": "Processing",
        "Arguments": {
            "RoleArn": role,
            "AppSpecification": {
                "ImageUri": image_uri,
                "ContainerEntrypoint": ["python3", entrypoint],
                "ContainerArguments": arguments,
            },
            "ProcessingResources": {
                "ClusterConfig": {
                    "InstanceType": instance_type,
                    "InstanceCount": 1,
                    "VolumeSizeInGB": 30,
                }
            },
            "ProcessingInputs": inputs,
            "ProcessingOutputConfig": {"Outputs": outputs},
            "StoppingCondition": {"MaxRuntimeInSeconds": 3600},
        },
    }


def _s3_input(name: str, source: Any, destination: str) -> dict[str, Any]:
    return {
        "InputName": name,
        "S3Input": {
            "S3Uri": source,
            "LocalPath": destination,
            "S3DataType": "S3Prefix",
            "S3InputMode": "File",
            "S3DataDistributionType": "FullyReplicated",
            "S3CompressionType": "None",
        },
    }


def _s3_file_input(name: str, source: str, destination: str) -> dict[str, Any]:
    item = _s3_input(name, source, destination)
    item["S3Input"]["S3DataType"] = "S3Prefix"
    return item


def _s3_output(name: str, source: str, destination: str) -> dict[str, Any]:
    return {
        "OutputName": name,
        "S3Output": {
            "S3Uri": destination,
            "LocalPath": source,
            "S3UploadMode": "EndOfJob",
        },
    }


def _training_step(
    config: LabConfig,
    image_uri: str,
    training_source_s3_uri: str,
    training_instance_type: str,
) -> dict[str, Any]:
    return {
        "Name": "TrainModel",
        "Type": "Training",
        "Arguments": {
            "RoleArn": config.sagemaker_execution_role_arn,
            "AlgorithmSpecification": {
                "TrainingImage": image_uri,
                "TrainingInputMode": "File",
            },
            "InputDataConfig": [
                {
                    "ChannelName": "train",
                    "DataSource": {
                        "S3DataSource": {
                            "S3Uri": {"Get": "Steps.ProcessData.ProcessingOutputConfig.Outputs['train'].S3Output.S3Uri"},
                            "S3DataType": "S3Prefix",
                            "S3DataDistributionType": "FullyReplicated",
                        }
                    },
                    "ContentType": "text/csv",
                }
            ],
            "OutputDataConfig": {"S3OutputPath": config.model_artifacts_s3_uri},
            "ResourceConfig": {
                "InstanceType": training_instance_type,
                "InstanceCount": 1,
                "VolumeSizeInGB": 30,
            },
            "StoppingCondition": {"MaxRuntimeInSeconds": 3600},
            "HyperParameters": {
                "sagemaker_program": json.dumps("train.py"),
                "sagemaker_submit_directory": json.dumps(training_source_s3_uri),
                "sagemaker_container_log_level": "20",
                "sagemaker_region": json.dumps(config.aws_region),
                "n-estimators": "120",
            },
        },
    }


def _register_model_step(config: LabConfig, image_uri: str, inference_instance_type: str) -> dict[str, Any]:
    inference_environment = {
        "SAGEMAKER_PROGRAM": "inference.py",
        "SAGEMAKER_SUBMIT_DIRECTORY": f"{config.artifacts_s3_uri}/source/training.tar.gz",
        "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
        "SAGEMAKER_REGION": config.aws_region,
    }
    return {
        "Name": "RegisterModel",
        "Type": "RegisterModel",
        "Arguments": {
            "ModelPackageGroupName": {"Get": "Parameters.ModelPackageGroupName"},
            "ModelApprovalStatus": "PendingManualApproval",
            "InferenceSpecification": {
                "Containers": [
                    {
                        "Image": image_uri,
                        "ModelDataUrl": {"Get": "Steps.TrainModel.ModelArtifacts.S3ModelArtifacts"},
                        "Environment": inference_environment,
                    }
                ],
                "SupportedContentTypes": ["application/json", "text/csv"],
                "SupportedResponseMIMETypes": ["application/json", "text/csv"],
                "SupportedRealtimeInferenceInstanceTypes": [inference_instance_type],
                "SupportedTransformInstanceTypes": [inference_instance_type],
            },
            "ModelMetrics": {
                "ModelQuality": {
                    "Statistics": {
                        "ContentType": "application/json",
                        "S3Uri": f"{config.evaluation_s3_uri}/evaluation.json",
                    }
                }
            },
        },
    }


def build_sagemaker_pipeline_definition(
    config: LabConfig,
    *,
    preprocess_code_s3_uri: str,
    evaluate_code_s3_uri: str,
    training_source_s3_uri: str,
    processing_instance_type: str | None = None,
    training_instance_type: str | None = None,
    inference_instance_type: str | None = None,
) -> dict[str, Any]:
    """Build a SageMaker Pipeline definition without depending on SDK v2 classes."""

    config.validate_for_cloud(require_execution_role=True)
    image_uri = _sklearn_image_uri(config)
    processing_instance_type = processing_instance_type or config.processing_instance_type
    training_instance_type = training_instance_type or config.training_instance_type
    inference_instance_type = inference_instance_type or config.instance_type

    process_step = _processing_step(
        name="ProcessData",
        role=config.sagemaker_execution_role_arn,
        image_uri=image_uri,
        instance_type=processing_instance_type,
        inputs=[
            _s3_input("raw-data", {"Get": "Parameters.InputDataUri"}, "/opt/ml/processing/input"),
            _s3_file_input("preprocess-code", preprocess_code_s3_uri, "/opt/ml/processing/code"),
        ],
        outputs=[
            _s3_output("train", "/opt/ml/processing/train", f"{config.processed_data_s3_uri}/train"),
            _s3_output("test", "/opt/ml/processing/test", f"{config.processed_data_s3_uri}/test"),
            _s3_output("baseline", "/opt/ml/processing/baseline", f"{config.raw_data_s3_uri}/baseline"),
        ],
        entrypoint="/opt/ml/processing/code/preprocess.py",
        arguments=[
            "--input-data",
            "/opt/ml/processing/input/churn_train.csv",
            "--train-output",
            "/opt/ml/processing/train/train.csv",
            "--test-output",
            "/opt/ml/processing/test/test.csv",
            "--baseline-output",
            "/opt/ml/processing/baseline/baseline.csv",
        ],
    )

    train_step = _training_step(config, image_uri, training_source_s3_uri, training_instance_type)

    evaluate_step = _processing_step(
        name="EvaluateModel",
        role=config.sagemaker_execution_role_arn,
        image_uri=image_uri,
        instance_type=processing_instance_type,
        inputs=[
            _s3_input("model", {"Get": "Steps.TrainModel.ModelArtifacts.S3ModelArtifacts"}, "/opt/ml/processing/model"),
            _s3_input("test", {"Get": "Steps.ProcessData.ProcessingOutputConfig.Outputs['test'].S3Output.S3Uri"}, "/opt/ml/processing/test"),
            _s3_file_input("evaluate-code", evaluate_code_s3_uri, "/opt/ml/processing/code"),
        ],
        outputs=[
            _s3_output("evaluation", "/opt/ml/processing/evaluation", config.evaluation_s3_uri),
        ],
        entrypoint="/opt/ml/processing/code/evaluate.py",
        arguments=[
            "--model-path",
            "/opt/ml/processing/model",
            "--test-data",
            "/opt/ml/processing/test/test.csv",
            "--output-path",
            "/opt/ml/processing/evaluation/evaluation.json",
        ],
    )
    evaluate_step["PropertyFiles"] = [
        {
            "PropertyFileName": "EvaluationReport",
            "OutputName": "evaluation",
            "FilePath": "evaluation.json",
        }
    ]

    quality_gate_step = {
        "Name": "QualityGate",
        "Type": "Condition",
        "Arguments": {
            "Conditions": [
                {
                    "Type": "GreaterThanOrEqualTo",
                    "LeftValue": {
                        "Std:JsonGet": {
                            "PropertyFile": {"Get": "Steps.EvaluateModel.PropertyFiles.EvaluationReport"},
                            "Path": "binary_classification_metrics.f1.value",
                        }
                    },
                    "RightValue": {"Get": "Parameters.F1Threshold"},
                },
                {
                    "Type": "GreaterThanOrEqualTo",
                    "LeftValue": {
                        "Std:JsonGet": {
                            "PropertyFile": {"Get": "Steps.EvaluateModel.PropertyFiles.EvaluationReport"},
                            "Path": "binary_classification_metrics.auc.value",
                        }
                    },
                    "RightValue": {"Get": "Parameters.AUCThreshold"},
                },
            ],
            "IfSteps": [_register_model_step(config, image_uri, inference_instance_type)],
            "ElseSteps": [],
        },
    }

    return {
        "Version": "2020-12-01",
        "Metadata": {
            "GeneratedBy": "5_MLOps",
            "PipelineMode": config.lab_mode,
            "Implementation": "boto3-low-level",
        },
        "Parameters": [
            {"Name": "InputDataUri", "Type": "String", "DefaultValue": f"{config.raw_data_s3_uri}/churn_train.csv"},
            {"Name": "F1Threshold", "Type": "Float", "DefaultValue": config.f1_threshold},
            {"Name": "AUCThreshold", "Type": "Float", "DefaultValue": config.auc_threshold},
            {"Name": "ModelPackageGroupName", "Type": "String", "DefaultValue": config.model_package_group_name},
        ],
        "Steps": [process_step, train_step, evaluate_step, quality_gate_step],
    }


def create_sagemaker_pipeline(config: LabConfig) -> dict[str, Any]:
    """Return the pipeline JSON definition for local inspection/tests."""

    return build_sagemaker_pipeline_definition(
        config,
        preprocess_code_s3_uri=f"{config.artifacts_s3_uri}/code/preprocess.py",
        evaluate_code_s3_uri=f"{config.artifacts_s3_uri}/code/evaluate.py",
        training_source_s3_uri=f"{config.artifacts_s3_uri}/source/training.tar.gz",
        processing_instance_type=config.processing_instance_type,
        training_instance_type=config.training_instance_type,
        inference_instance_type=config.instance_type,
    )


def _ensure_pipeline_compute_available(compute: dict[str, Any]) -> None:
    blocked = [
        item
        for item in (compute.get("processing", {}), compute.get("training", {}))
        if item.get("source") == "fallback-no-positive-quota"
    ]
    if not blocked:
        return
    details = []
    for item in blocked:
        notes = " ".join(str(note) for note in item.get("notes", []))
        details.append(
            f"- {item.get('workload')}: selected={item.get('selected_instance_type')} "
            f"candidates={', '.join(item.get('candidates', []))}. {notes}"
        )
    raise RuntimeError(
        "No SageMaker quota is available for required pipeline compute.\n"
        + "\n".join(details)
        + "\n\nRun `python -m src.compute`, update PROCESSING_INSTANCE_TYPE_CANDIDATES "
        "or TRAINING_INSTANCE_TYPE_CANDIDATES with an instance that has quota, "
        "or request a SageMaker Service Quotas increase."
    )


def upsert_pipeline(config: LabConfig) -> dict[str, Any]:
    clients = create_clients(config)
    compute = resolve_pipeline_compute(config, clients.session)
    _ensure_pipeline_compute_available(compute)
    processing_instance_type = compute["processing"]["selected_instance_type"]
    training_instance_type = compute["training"]["selected_instance_type"]
    inference_instance_type = compute["endpoint"]["selected_instance_type"]
    preprocess_code_s3_uri = _upload_file(
        clients.s3,
        Path("processing/preprocess.py"),
        f"{config.artifacts_s3_uri}/code/preprocess.py",
    )
    evaluate_code_s3_uri = _upload_file(
        clients.s3,
        Path("processing/evaluate.py"),
        f"{config.artifacts_s3_uri}/code/evaluate.py",
    )
    training_source_s3_uri = _upload_training_source(clients.s3, config)
    definition = build_sagemaker_pipeline_definition(
        config,
        preprocess_code_s3_uri=preprocess_code_s3_uri,
        evaluate_code_s3_uri=evaluate_code_s3_uri,
        training_source_s3_uri=training_source_s3_uri,
        processing_instance_type=processing_instance_type,
        training_instance_type=training_instance_type,
        inference_instance_type=inference_instance_type,
    )
    definition_body = json.dumps(definition, indent=2)
    definition_path = config.local_outputs_dir / "sagemaker_pipeline_definition.json"
    definition_path.write_text(definition_body + "\n", encoding="utf-8")

    pipeline_exists = False
    try:
        clients.sagemaker.describe_pipeline(PipelineName=config.pipeline_name)
        pipeline_exists = True
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code not in {"ValidationException", "ResourceNotFound"}:
            raise

    if pipeline_exists:
        response = clients.sagemaker.update_pipeline(
            PipelineName=config.pipeline_name,
            PipelineDefinition=definition_body,
            RoleArn=config.sagemaker_execution_role_arn,
        )
        status = "updated"
    else:
        response = clients.sagemaker.create_pipeline(
            PipelineName=config.pipeline_name,
            PipelineDisplayName=config.pipeline_name,
            PipelineDefinition=definition_body,
            RoleArn=config.sagemaker_execution_role_arn,
            Tags=config.tags,
        )
        status = "created"

    save_pipeline_contract(config)
    return {
        "status": status,
        "pipeline_name": config.pipeline_name,
        "pipeline_definition_path": str(definition_path),
        "uploaded_assets": {
            "preprocess_code": preprocess_code_s3_uri,
            "evaluate_code": evaluate_code_s3_uri,
            "training_source": training_source_s3_uri,
        },
        "compute_selection": compute,
        "service_response": response,
    }
