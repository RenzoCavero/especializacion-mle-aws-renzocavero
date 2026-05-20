from src.cleanup_batch_resources import is_lab_s3_uri
from src.config import LabConfig


def _config(bucket="lab-bucket", prefix="ml-deploy-lab/lab"):
    return LabConfig(
        lab_mode="standalone",
        aws_profile="",
        aws_region="us-east-1",
        project_name="ml-model-deployment",
        environment="lab",
        resource_prefix="ml-deploy-lab",
        stack_name="ml-deploy-lab",
        s3_bucket_name=bucket,
        s3_prefix=prefix,
        sagemaker_execution_role_arn="arn:aws:iam::123456789012:role/example",
        model_package_group_name="",
        model_package_arn="",
        model_artifact_s3_uri="",
        feature_group_name="",
        offline_store_s3_uri="",
        feature_contract_s3_uri="",
        create_standalone_model=True,
        create_standalone_feature_group=False,
        endpoint_name="ml-deploy-realtime-endpoint",
        endpoint_config_name="ml-deploy-realtime-config",
        model_name="ml-deploy-model",
        batch_job_prefix="ml-deploy-batch",
        instance_type="ml.m5.large",
        initial_instance_count=1,
        batch_instance_type="ml.m5.large",
        batch_instance_count=1,
        split_type="Line",
        batch_strategy="SingleRecord",
        max_payload_mb=6,
        max_concurrent_transforms=1,
        enable_data_capture=True,
        enable_autoscaling=True,
        autoscaling_min_capacity=1,
        autoscaling_max_capacity=2,
        autoscaling_target_invocations_per_instance=50.0,
        wait_for_batch=True,
        wait_for_endpoint=True,
        realtime_record_id="",
        inference_image_uri="",
        kms_key_id="",
        delete_lab_s3=False,
    )


def test_cleanup_allows_only_lab_prefix():
    config = _config()
    assert is_lab_s3_uri(config, "s3://lab-bucket/ml-deploy-lab/lab/batch/output/job")
    assert not is_lab_s3_uri(config, "s3://lab-bucket/other-prefix/output")
    assert not is_lab_s3_uri(config, "s3://other-bucket/ml-deploy-lab/lab/batch/output")
