"""Decision policy for drift and monitoring violations."""

from __future__ import annotations


VALID_ACTIONS = {"retraining", "rollback", "baseline_update", "human_review", "no_action"}


def decide_action(violations_count: int = 0, severity: str = "low", automatic_retraining: bool = False) -> str:
    severity = severity.lower()
    if violations_count <= 0:
        return "no_action"
    if severity in {"critical", "high"}:
        return "retraining" if automatic_retraining else "human_review"
    if severity == "medium":
        return "baseline_update"
    return "human_review"


def describe_action(action: str) -> str:
    descriptions = {
        "retraining": "Trigger controlled retraining because automatic retraining is enabled.",
        "rollback": "Prepare rollback to a previous approved model.",
        "baseline_update": "Prepare baseline update after evidence review.",
        "human_review": "Stop automation and request human review.",
        "no_action": "Record evidence and close without operational change.",
    }
    return descriptions.get(action, "Unknown action.")

