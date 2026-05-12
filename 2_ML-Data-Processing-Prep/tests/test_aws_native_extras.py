from botocore.exceptions import ClientError

from src.config import get_settings
from src.destroy_infra import _empty_bucket
from src.glue_catalog import catalog_location, catalog_object_key, sync_catalog_data, table_input
from src.run_glue_column_statistics import COLUMN_NAMES, _format_column_statistics_failure
from src.run_glue_crawler import RAW_TO_CRAWLER_DEMO
from src.run_glue_data_quality import FEATURES_TRAINING_RULESET, _format_failure_message
from src.schemas import S3_ZONES


def test_glue_crawler_demo_uses_separate_prefixes_per_raw_dataset():
    assert RAW_TO_CRAWLER_DEMO == {
        "raw/customers.csv": "crawler_demo/customers/customers.csv",
        "raw/transactions.csv": "crawler_demo/transactions/transactions.csv",
        "raw/inference_transactions.csv": "crawler_demo/inference_transactions/inference_transactions.csv",
    }


def test_glue_catalog_locations_use_folder_prefixes_for_athena():
    payload = table_input("features_training", "example-bucket")

    assert payload["StorageDescriptor"]["Location"] == "s3://example-bucket/features/training_dataset/"
    assert catalog_location("raw_transactions", "example-bucket") == "s3://example-bucket/raw/transactions/"
    assert catalog_object_key("features_training") == "features/training_dataset/training_dataset.csv"


def test_sync_catalog_data_copies_existing_files_and_skips_missing_outputs():
    class FakeS3:
        def __init__(self):
            self.existing = {"features/training_dataset.csv"}
            self.copied = []

        def head_object(self, Bucket, Key):
            if Key not in self.existing:
                raise ClientError({"Error": {"Code": "404", "Message": "Not found"}}, "HeadObject")

        def copy_object(self, Bucket, CopySource, Key):
            self.copied.append((CopySource["Key"], Key))
            self.existing.add(Key)

    s3 = FakeS3()
    synced = sync_catalog_data(s3, "example-bucket", ["features_training", "features_inference"])

    assert synced == ["features/training_dataset/training_dataset.csv"]
    assert s3.copied == [("features/training_dataset.csv", "features/training_dataset/training_dataset.csv")]


def test_glue_data_quality_ruleset_checks_training_dataset_contract():
    assert 'IsComplete "transaction_id"' in FEATURES_TRAINING_RULESET
    assert 'IsComplete "customer_id"' in FEATURES_TRAINING_RULESET
    assert 'ColumnValues "amount" > 0' in FEATURES_TRAINING_RULESET
    assert 'ColumnValues "is_fraud" in [0, 1]' in FEATURES_TRAINING_RULESET
    assert 'ColumnValues "split" in ["train", "validation", "test"]' in FEATURES_TRAINING_RULESET


def test_column_statistics_targets_feature_columns_and_optional_zones_exist():
    assert {"amount", "amount_log", "customer_txn_count", "amount_to_customer_avg", "is_fraud", "split"}.issubset(
        set(COLUMN_NAMES)
    )
    assert "crawler_demo" in S3_ZONES
    assert "athena-results" in S3_ZONES


def test_empty_optional_glue_names_fall_back_to_resource_prefix(monkeypatch):
    monkeypatch.setenv("RESOURCE_PREFIX", "example-prefix")
    monkeypatch.setenv("GLUE_CRAWLER_NAME", "")
    monkeypatch.setenv("GLUE_DATA_QUALITY_RULESET_NAME", "")

    settings = get_settings(load_env=False)

    assert settings.glue_crawler_name == "example-prefix-raw-crawler"
    assert settings.glue_data_quality_ruleset_name == "example-prefix-features-training-quality"


def test_empty_bucket_continues_when_bucket_does_not_exist():
    class MissingBucketPaginator:
        def paginate(self, **_kwargs):
            raise ClientError(
                {"Error": {"Code": "NoSuchBucket", "Message": "The specified bucket does not exist"}},
                "ListObjectVersions",
            )

    class MissingBucketS3:
        def get_paginator(self, _name):
            return MissingBucketPaginator()

    _empty_bucket(MissingBucketS3(), "missing-bucket")


def test_glue_data_quality_asset_access_denied_message_is_actionable():
    message = _format_failure_message(
        "FAILED",
        {
            "Role": "arn:aws:iam::123456789012:role/example-glue-role",
            "ErrorString": (
                "LAUNCH ERROR | Error downloading from S3 for bucket: "
                "aws-glue-ml-data-quality-assets-us-east-1, key: jars/aws-glue-ml-data-quality-etl.jar."
                "Access Denied"
            ),
        },
    )

    assert "s3:GetObject" in message
    assert "aws-glue-ml-data-quality-assets-<region>/*" in message
    assert "bash scripts/deploy_infra.sh" in message


def test_glue_data_quality_ruleset_access_denied_message_is_actionable():
    message = _format_failure_message(
        "FAILED",
        {
            "Role": "arn:aws:iam::123456789012:role/example-glue-role",
            "ErrorString": (
                "AccessDeniedException: not authorized to perform: "
                "glue:GetDataQualityRulesetEvaluationRun on resource: "
                "arn:aws:glue:us-east-1:123456789012:dataQualityRuleset/example"
            ),
        },
    )

    assert "glue:GetDataQualityRulesetEvaluationRun" in message
    assert "glue:PublishDataQuality" in message
    assert "dataQualityRuleset/*" in message
    assert "bash scripts/deploy_infra.sh" in message


def test_column_statistics_s3_access_message_is_actionable():
    message = _format_column_statistics_failure(
        "FAILED",
        "Unable to Validate access to underlying S3 path. Please ensure role has appropriate permissions.",
    )

    assert "s3:ListBucket" in message
    assert "s3:GetObject" in message
    assert "bash scripts/deploy_infra.sh" in message
