from __future__ import annotations

from types import SimpleNamespace

from src import create_batch_cloudwatch_alarm


class FakeCloudWatch:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def put_metric_alarm(self, **kwargs):
        self.requests.append(kwargs)


def test_batch_alarm_is_created_for_manual_custom_metric_even_when_native_exists(monkeypatch):
    cloudwatch = FakeCloudWatch()
    config = SimpleNamespace(
        enable_cloudwatch_alarm=True,
        custom_batch_data_quality_alarm_name="mlops-custom-batch-data-quality-alarm",
        batch_violations_metric_name="BatchDataQualityViolations",
        batch_monitoring_schedule_name="mlops-lab-batch-monitoring-schedule",
        metric_namespace="MLOps/Lab",
        alarm_period_seconds=300,
        alarm_evaluation_periods=1,
        alarm_datapoints_to_alarm=1,
        alarm_threshold=1.0,
        alarm_treat_missing_data="notBreaching",
        tags=[],
    )
    written: dict[str, object] = {}

    monkeypatch.setattr(create_batch_cloudwatch_alarm, "load_config", lambda validate=True: config)
    monkeypatch.setattr(
        create_batch_cloudwatch_alarm,
        "create_clients",
        lambda cfg: SimpleNamespace(cloudwatch=cloudwatch),
    )
    monkeypatch.setattr(
        create_batch_cloudwatch_alarm,
        "read_metadata",
        lambda cfg, name: {"status": "created"} if name == "batch_monitoring_schedule" else {},
    )
    monkeypatch.setattr(
        create_batch_cloudwatch_alarm,
        "write_metadata",
        lambda cfg, name, payload: written.update({"name": name, "payload": payload}),
    )

    payload = create_batch_cloudwatch_alarm.create_batch_alarm()

    assert cloudwatch.requests
    assert payload["active_alarm_route"] == "custom_batch_manual_test_metric"
    assert payload["metric_name"] == "BatchDataQualityViolations"
    assert payload["dimensions"] == [
        {"Name": "BatchMonitoringSchedule", "Value": "mlops-lab-batch-monitoring-schedule"}
    ]
    assert written["name"] == "batch_cloudwatch_alarm"
