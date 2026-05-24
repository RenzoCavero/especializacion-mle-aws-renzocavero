from __future__ import annotations

import json
from pathlib import Path

from monitoring.drift_policy import decide_action


def test_feedback_loop_decision_actions():
    assert decide_action(0, "none", False) == "no_action"
    assert decide_action(1, "low", False) == "human_review"
    assert decide_action(3, "medium", False) == "baseline_update"
    assert decide_action(8, "high", False) == "human_review"
    assert decide_action(8, "high", True) == "retraining"


def test_step_functions_definition_has_all_branches():
    definition = json.loads(Path("stepfunctions/feedback_loop.asl.json").read_text(encoding="utf-8"))
    states = definition["States"]
    for state in ["DiagnoseAlert", "DecideAction", "Retraining", "Rollback", "BaselineUpdate", "HumanReview", "NoAction", "RecordDecision"]:
        assert state in states

