"""Safe rollback placeholder."""

from __future__ import annotations

from datetime import datetime, timezone


def lambda_handler(event, context):
    return {
        "action": "rollback",
        "status": "planned",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "message": "Rollback is intentionally a safe placeholder. Review previous Approved model before changing traffic.",
        "evidence": event,
    }

