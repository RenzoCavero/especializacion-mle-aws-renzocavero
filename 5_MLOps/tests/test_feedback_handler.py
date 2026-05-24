from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _handler_module():
    path = Path("lambdas/feedback_handler/lambda_function.py")
    spec = importlib.util.spec_from_file_location("feedback_lambda_function", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_feedback_handler_infers_data_quality_severity_from_cloudwatch_datapoint(monkeypatch):
    module = _handler_module()
    monkeypatch.setenv("ENABLE_AUTOMATIC_RETRAINING", "false")
    event = {
        "detail": {
            "alarmName": "mlops-custom-data-quality-alarm",
            "state": {"reasonData": json.dumps({"threshold": 1.0, "recentDatapoints": [6.0]})},
            "configuration": {
                "metrics": [
                    {
                        "metricStat": {
                            "metric": {
                                "namespace": "MLOps/Lab",
                                "name": "DataQualityViolations",
                                "dimensions": {"EndpointName": "mlops-lab-endpoint"},
                            }
                        }
                    }
                ]
            },
        }
    }

    result = module.lambda_handler(event, None)

    assert result["alarm_type"] == "data_quality"
    assert result["violations_count"] == 6
    assert result["severity"] == "high"
    assert result["recommended_action"] == "human_review"


def test_feedback_handler_treats_batch_violations_as_data_quality(monkeypatch):
    module = _handler_module()
    monkeypatch.setenv("ENABLE_AUTOMATIC_RETRAINING", "false")
    event = {
        "detail": {
            "alarmName": "mlops-custom-batch-data-quality-alarm",
            "state": {"reasonData": json.dumps({"threshold": 1.0, "recentDatapoints": [3.0]})},
            "configuration": {
                "metrics": [
                    {
                        "metricStat": {
                            "metric": {
                                "namespace": "MLOps/Lab",
                                "name": "BatchDataQualityViolations",
                                "dimensions": {"BatchMonitoringSchedule": "mlops-lab-batch-monitoring-schedule"},
                            }
                        }
                    }
                ]
            },
        }
    }

    result = module.lambda_handler(event, None)

    assert result["alarm_type"] == "data_quality"
    assert result["endpoint_name"] == "mlops-lab-batch-monitoring-schedule"
    assert result["violations_count"] == 3
    assert result["severity"] == "medium"
    assert result["recommended_action"] == "baseline_update"


def test_feedback_handler_infers_model_quality_degradation_from_f1(monkeypatch):
    module = _handler_module()
    monkeypatch.setenv("ENABLE_AUTOMATIC_RETRAINING", "true")
    event = {
        "detail": {
            "alarmName": "mlops-custom-model-quality-alarm",
            "state": {"reasonData": json.dumps({"threshold": 0.7, "recentDatapoints": [0.3]})},
            "configuration": {
                "metrics": [
                    {
                        "metricStat": {
                            "metric": {
                                "namespace": "MLOps/Lab",
                                "name": "ModelQualityF1",
                                "dimensions": {"EndpointName": "mlops-lab-endpoint"},
                            }
                        }
                    }
                ]
            },
        }
    }

    result = module.lambda_handler(event, None)

    assert result["alarm_type"] == "model_quality"
    assert result["severity"] == "critical"
    assert result["diagnosis"]["model_quality_degradation_pct"] == 57.14
    assert result["recommended_action"] == "retraining"
