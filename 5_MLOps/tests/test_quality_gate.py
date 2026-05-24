from __future__ import annotations

from pipelines.build.quality_gate import approval_status_for_metrics, evaluate_quality_gate


def test_quality_gate_passes_good_metrics():
    result = evaluate_quality_gate({"f1": 0.81, "auc": 0.84})
    assert result.passed
    assert result.reasons == []
    assert approval_status_for_metrics({"f1": 0.81, "auc": 0.84}) == "Approved"


def test_quality_gate_rejects_low_metrics():
    result = evaluate_quality_gate({"f1": 0.55, "auc": 0.69})
    assert not result.passed
    assert len(result.reasons) == 2
    assert approval_status_for_metrics({"f1": 0.55, "auc": 0.69}) == "Rejected"

