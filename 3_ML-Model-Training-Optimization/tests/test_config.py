from src import config
from src.config import s3_join, sdk_local_path


def test_s3_join() -> None:
    assert s3_join("my-bucket", "a", "/b/", "c.txt") == "s3://my-bucket/a/b/c.txt"
    assert s3_join("my-bucket") == "s3://my-bucket"


def test_sdk_local_path_is_relative_and_posix() -> None:
    assert sdk_local_path("processing", "processing_entrypoint.py") == "processing/processing_entrypoint.py"
    sdk_path = sdk_local_path("training")
    assert sdk_path == "training"
    assert ":" not in sdk_path
    assert "\\" not in sdk_path


def test_load_env_file_ignores_empty_values_and_fills_missing(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    generated_file = tmp_path / ".env.cloud"
    env_file.write_text(
        "S3_BUCKET_NAME=\n"
        "AWS_REGION=us-east-1\n"
        "SAGEMAKER_EXECUTION_ROLE_ARN=\n",
        encoding="utf-8",
    )
    generated_file.write_text(
        "S3_BUCKET_NAME=generated-bucket\n"
        "SAGEMAKER_EXECUTION_ROLE_ARN=arn:aws:iam::123456789012:role/generated\n",
        encoding="utf-8",
    )

    for name in ("S3_BUCKET_NAME", "AWS_REGION", "SAGEMAKER_EXECUTION_ROLE_ARN"):
        monkeypatch.delenv(name, raising=False)

    config._load_env_file(env_file)
    config._load_env_file(generated_file)

    assert config.os.environ["AWS_REGION"] == "us-east-1"
    assert config.os.environ["S3_BUCKET_NAME"] == "generated-bucket"
    assert (
        config.os.environ["SAGEMAKER_EXECUTION_ROLE_ARN"]
        == "arn:aws:iam::123456789012:role/generated"
    )


def test_load_env_file_keeps_existing_non_empty_values(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env.cloud"
    env_file.write_text("S3_BUCKET_NAME=generated-bucket\n", encoding="utf-8")
    monkeypatch.setenv("S3_BUCKET_NAME", "explicit-bucket")

    config._load_env_file(env_file)

    assert config.os.environ["S3_BUCKET_NAME"] == "explicit-bucket"
