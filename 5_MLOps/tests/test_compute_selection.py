from __future__ import annotations

from datetime import datetime, timezone

from src.compute import build_quota_inventory, select_instance_type
from src.config import LabConfig


class FakePaginator:
    def paginate(self, ServiceCode: str):
        assert ServiceCode == "sagemaker"
        return [
            {
                "Quotas": [
                    {"QuotaName": "ml.m5.large for processing job usage", "Value": 0.0},
                    {"QuotaName": "ml.c6i.xlarge for processing job usage", "Value": 2.0},
                    {"QuotaName": "ml.c6i.large for transform job usage", "Value": 3.0},
                ]
            }
        ]


class FakeServiceQuotas:
    def get_paginator(self, name: str):
        assert name == "list_service_quotas"
        return FakePaginator()


class FakeShape:
    def __init__(self, enum: list[str]):
        self.enum = enum


class FakeServiceModel:
    def shape_for(self, name: str):
        if name == "ProcessingInstanceType":
            return FakeShape(["ml.m5.large", "ml.m6i.large", "ml.c6i.xlarge", "ml.t3.medium"])
        if name == "TransformInstanceType":
            return FakeShape(["ml.c6i.large", "ml.m6i.large", "ml.m5.xlarge", "ml.m5.large"])
        return FakeShape(["ml.m5.large", "ml.m6i.large", "ml.c6i.xlarge", "ml.t3.medium"])


class FakeMeta:
    service_model = FakeServiceModel()


class FakeSession:
    meta = FakeMeta()

    def client(self, service_name: str):
        if service_name == "sagemaker":
            return self
        assert service_name == "service-quotas"
        return FakeServiceQuotas()


class FakeTrainingPositivePaginator:
    def paginate(self, ServiceCode: str):
        assert ServiceCode == "sagemaker"
        return [
            {
                "Quotas": [
                    {"QuotaName": "ml.m5.large for training job usage", "Value": 0.0},
                    {"QuotaName": "ml.m6i.large for training job usage", "Value": 1.0},
                ]
            }
        ]


class FakeTrainingPositiveServiceQuotas:
    def get_paginator(self, name: str):
        assert name == "list_service_quotas"
        return FakeTrainingPositivePaginator()


class FakeTrainingPositiveSession(FakeSession):
    def client(self, service_name: str):
        if service_name == "sagemaker":
            return self
        assert service_name == "service-quotas"
        return FakeTrainingPositiveServiceQuotas()


class FakeTrainingRecentSuccessPaginator:
    def paginate(self, ServiceCode: str):
        assert ServiceCode == "sagemaker"
        return [
            {
                "Quotas": [
                    {"QuotaName": "ml.m5.large for training job usage", "Value": 0.0},
                    {"QuotaName": "ml.m6i.large for training job usage", "Value": 0.0},
                ]
            }
        ]


class FakeTrainingRecentSuccessServiceQuotas:
    def get_paginator(self, name: str):
        assert name == "list_service_quotas"
        return FakeTrainingRecentSuccessPaginator()


class FakeTrainingRecentSuccessSession(FakeSession):
    def client(self, service_name: str):
        if service_name == "sagemaker":
            return self
        assert service_name == "service-quotas"
        return FakeTrainingRecentSuccessServiceQuotas()

    def list_training_jobs(self, **kwargs):
        assert kwargs["StatusEquals"] == "Completed"
        return {
            "TrainingJobSummaries": [
                {
                    "TrainingJobName": "ml-train-hpo-0520023251-m5-large-004-7444bf7c",
                    "CreationTime": datetime.now(timezone.utc),
                }
            ]
        }

    def describe_training_job(self, TrainingJobName: str):
        assert TrainingJobName == "ml-train-hpo-0520023251-m5-large-004-7444bf7c"
        return {
            "TrainingJobName": TrainingJobName,
            "TrainingJobStatus": "Completed",
            "CreationTime": datetime.now(timezone.utc),
            "ResourceConfig": {"InstanceType": "ml.m5.large"},
        }


def test_compute_selection_skips_zero_quota_candidate():
    cfg = LabConfig(auto_select_compute=True)
    selected = select_instance_type(
        cfg,
        workload="processing",
        preferred="ml.m5.large",
        candidates=["ml.m5.large", "ml.c6i.xlarge"],
        session=FakeSession(),
    )
    assert selected.selected_instance_type == "ml.c6i.xlarge"
    assert selected.quota_value == 2.0


def test_compute_selection_can_be_disabled():
    cfg = LabConfig(auto_select_compute=False)
    selected = select_instance_type(
        cfg,
        workload="processing",
        preferred="ml.m5.large",
        candidates=["ml.c6i.large", "ml.m5.large"],
        session=FakeSession(),
    )
    assert selected.selected_instance_type == "ml.m5.large"
    assert selected.source == "AUTO_SELECT_COMPUTE=false"


def test_compute_selection_filters_invalid_processing_candidate():
    cfg = LabConfig(auto_select_compute=True)
    selected = select_instance_type(
        cfg,
        workload="processing",
        preferred="ml.m5.large",
        candidates=["ml.c6i.large", "ml.m5.large", "ml.c6i.xlarge"],
        session=FakeSession(),
    )
    assert selected.selected_instance_type == "ml.c6i.xlarge"
    assert all(candidate != "ml.c6i.large" for candidate in selected.candidates)
    assert any("Invalid candidates ignored" in note for note in selected.notes)


def test_compute_selection_supports_batch_transform_alias():
    cfg = LabConfig(auto_select_compute=True)
    selected = select_instance_type(
        cfg,
        workload="batch-transform",
        preferred="ml.m5.large",
        candidates=["ml.c6i.large", "ml.m5.large"],
        session=FakeSession(),
    )
    assert selected.workload == "batch_transform"
    assert selected.selected_instance_type == "ml.c6i.large"
    assert selected.quota_value == 3.0


def test_compute_inventory_lists_batch_transform_supported_types():
    cfg = LabConfig(auto_select_compute=True)
    inventory = build_quota_inventory(
        cfg,
        workload="batch-transform",
        session=FakeSession(),
        limit=0,
    )
    assert inventory["workload"] == "batch_transform"
    assert inventory["supported_instance_type_count"] == 4
    assert inventory["positive_quota_count"] == 1
    assert inventory["positive_quota_instance_types"][0]["instance_type"] == "ml.c6i.large"


def test_training_unknown_quota_is_not_selected_for_pipeline_jobs():
    cfg = LabConfig(auto_select_compute=True)
    selected = select_instance_type(
        cfg,
        workload="training",
        preferred="ml.m5.large",
        candidates=["ml.t3.medium", "ml.m5.large"],
        session=FakeSession(),
    )
    assert selected.source == "fallback-no-positive-quota"
    assert selected.quota_value == 0.0
    assert any("Unknown quota candidates were not selected automatically" in note for note in selected.notes)


def test_training_can_select_positive_quota_outside_configured_candidates():
    cfg = LabConfig(auto_select_compute=True)
    selected = select_instance_type(
        cfg,
        workload="training",
        preferred="ml.m5.large",
        candidates=["ml.m5.large"],
        session=FakeTrainingPositiveSession(),
    )
    assert selected.selected_instance_type == "ml.m6i.large"
    assert selected.source == "service-quotas-outside-candidates"
    assert selected.quota_value == 1.0


def test_training_can_use_recent_completed_job_as_best_effort_evidence():
    cfg = LabConfig(auto_select_compute=True)
    selected = select_instance_type(
        cfg,
        workload="training",
        preferred="ml.m5.large",
        candidates=["ml.m6i.large", "ml.m5.large"],
        session=FakeTrainingRecentSuccessSession(),
    )
    assert selected.selected_instance_type == "ml.m5.large"
    assert selected.source == "recent-successful-training-job"
    assert any("recent completed Training Job" in note for note in selected.notes)
