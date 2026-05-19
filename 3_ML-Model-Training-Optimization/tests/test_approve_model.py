from src.approve_model import default_deployable_model_name, version_from_model_package_arn


def test_version_from_model_package_arn() -> None:
    arn = "arn:aws:sagemaker:us-east-1:123456789012:model-package/churn-model-package-group/12"

    assert version_from_model_package_arn(arn) == "12"


def test_default_deployable_model_name_uses_registry_version() -> None:
    arn = "arn:aws:sagemaker:us-east-1:123456789012:model-package/churn-model-package-group/3"

    assert default_deployable_model_name("ml-training-opt-lab", arn) == "ml-training-opt-lab-deployable-v3"


def test_default_deployable_model_name_stays_within_sagemaker_limit() -> None:
    arn = "arn:aws:sagemaker:us-east-1:123456789012:model-package/group-name/123456789"
    name = default_deployable_model_name("this-prefix-is-intentionally-very-long-for-a-lab", arn)

    assert len(name) <= 63
    assert not name.endswith("-")
