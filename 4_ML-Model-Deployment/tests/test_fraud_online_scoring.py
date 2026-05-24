from fraud_lab.config import default_online_transaction
from fraud_lab.feature_store.seed_feature_store import seed_feature_store
from fraud_lab.scoring.fraud_scoring_service import FraudScoringService


def test_online_scoring_persists_logs_and_emits_event(monkeypatch, tmp_path):
    monkeypatch.setenv("FRAUD_LAB_ROOT", str(tmp_path))
    seed_feature_store()

    result = FraudScoringService().score_transaction(default_online_transaction())

    assert "fraud_score" in result
    assert result["decision"] in {"approve", "manual_review", "reject"}
    assert (tmp_path / "data" / "operational" / "decisions" / "T001.json").exists()
    assert list((tmp_path / "data" / "events" / "pending").glob("*.json"))

