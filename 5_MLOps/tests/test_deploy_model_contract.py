from __future__ import annotations

from src.config import LabConfig
from src.deploy_model import _inference_environment


def test_deployment_container_environment_points_to_inference_entrypoint():
    cfg = LabConfig(aws_region="us-east-1", s3_bucket_name="example-bucket")
    environment = _inference_environment(cfg, "s3://example-bucket/source/inference.tar.gz")
    assert environment == {
        "SAGEMAKER_PROGRAM": "inference.py",
        "SAGEMAKER_SUBMIT_DIRECTORY": "s3://example-bucket/source/inference.tar.gz",
        "SAGEMAKER_CONTAINER_LOG_LEVEL": "20",
        "SAGEMAKER_REGION": "us-east-1",
    }
