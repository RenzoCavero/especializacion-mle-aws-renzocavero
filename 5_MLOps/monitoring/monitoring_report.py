"""Create a local markdown report for monitoring results."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def write_monitoring_report(path: Path, summary: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Monitoring Report",
        "",
        f"- Endpoint: `{summary.get('endpoint_name', '')}`",
        f"- Violations count: `{summary.get('violations_count', 0)}`",
        f"- Severity: `{summary.get('severity', 'none')}`",
        f"- Latest violations URI: `{summary.get('latest_violations_uri', '')}`",
        "",
        "## Notes",
        "",
        "Review violations before triggering retraining, rollback or baseline update.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path

