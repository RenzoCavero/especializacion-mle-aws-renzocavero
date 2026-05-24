from __future__ import annotations

from src.check_pipeline_execution import build_recommendations


def test_pipeline_failure_recommends_training_inventory():
    recommendations = build_recommendations(
        [
            {
                "StepName": "TrainModel",
                "FailureReason": "The requested resource training-job/ml.t3.medium is not available in this region",
            }
        ]
    )
    assert recommendations
    assert "src.compute --workload training --inventory" in recommendations[0]


def test_quality_gate_false_recommends_rerun_data_and_pipeline():
    recommendations = build_recommendations(
        [
            {
                "StepName": "QualityGate",
                "StepStatus": "Succeeded",
                "Metadata": {"Condition": {"Outcome": "False"}},
            }
        ]
    )
    assert recommendations
    assert "QualityGate outcome was False" in recommendations[0]
    assert "src.lab_runner step 02" in recommendations[0]
