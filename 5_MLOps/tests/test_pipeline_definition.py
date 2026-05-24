from __future__ import annotations

from src.config import LabConfig, load_config
from pipelines.build.pipeline_definition import build_pipeline_contract, build_sagemaker_pipeline_definition


def test_pipeline_contract_contains_required_steps(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    cfg = load_config(validate=True)
    contract = build_pipeline_contract(cfg)
    assert contract["steps"] == ["process", "train", "evaluate", "quality_gate", "register"]
    assert contract["quality_gate"]["metric_rules"]


def test_low_level_pipeline_definition_contains_register_gate():
    cfg = LabConfig(
        aws_region="us-east-1",
        s3_bucket_name="example-bucket",
        sagemaker_execution_role_arn="arn:aws:iam::123456789012:role/SageMakerRole",
    )
    definition = build_sagemaker_pipeline_definition(
        cfg,
        preprocess_code_s3_uri="s3://example-bucket/code/preprocess.py",
        evaluate_code_s3_uri="s3://example-bucket/code/evaluate.py",
        training_source_s3_uri="s3://example-bucket/source/training.tar.gz",
        processing_instance_type="ml.c6i.xlarge",
        training_instance_type="ml.m6i.large",
        inference_instance_type="ml.m5.xlarge",
    )
    assert [step["Type"] for step in definition["Steps"]] == ["Processing", "Training", "Processing", "Condition"]
    assert definition["Steps"][0]["Arguments"]["ProcessingResources"]["ClusterConfig"]["InstanceType"] == "ml.c6i.xlarge"
    assert definition["Steps"][1]["Arguments"]["ResourceConfig"]["InstanceType"] == "ml.m6i.large"
    gate = definition["Steps"][-1]
    assert gate["Name"] == "QualityGate"
    assert gate["Arguments"]["IfSteps"][0]["Type"] == "RegisterModel"
    register_args = gate["Arguments"]["IfSteps"][0]["Arguments"]
    supported_instances = register_args["InferenceSpecification"]["SupportedRealtimeInferenceInstanceTypes"]
    container = register_args["InferenceSpecification"]["Containers"][0]
    assert supported_instances == ["ml.m5.xlarge"]
    assert container["Environment"]["SAGEMAKER_PROGRAM"] == "inference.py"
    assert container["Environment"]["SAGEMAKER_SUBMIT_DIRECTORY"] == "s3://example-bucket/mlops-lab/lab/artifacts/source/training.tar.gz"
