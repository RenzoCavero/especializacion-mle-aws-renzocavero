"""Safe baseline update placeholder."""

from __future__ import annotations

from datetime import datetime, timezone


def lambda_handler(event, context):
    return {
        "action": "baseline_update",
        "status": "planned",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "message": "Baseline update requires evidence review and explicit execution outside the default flow.",
        "evidence": event,
    }

