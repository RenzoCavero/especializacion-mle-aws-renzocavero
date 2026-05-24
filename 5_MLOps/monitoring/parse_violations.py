"""Parse SageMaker Model Monitor constraints_violations.json files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_violations(payload: dict[str, Any]) -> dict[str, Any]:
    violations = payload.get("violations", [])
    by_feature: dict[str, int] = {}
    for item in violations:
        feature = item.get("feature_name") or item.get("feature") or "unknown"
        by_feature[feature] = by_feature.get(feature, 0) + 1
    severity = "none"
    count = len(violations)
    if count >= 10:
        severity = "critical"
    elif count >= 5:
        severity = "high"
    elif count >= 2:
        severity = "medium"
    elif count == 1:
        severity = "low"
    return {"violations_count": count, "severity": severity, "by_feature": by_feature, "violations": violations}


def parse_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_violations(payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args()
    print(json.dumps(parse_file(Path(args.path)), indent=2))


if __name__ == "__main__":
    main()
