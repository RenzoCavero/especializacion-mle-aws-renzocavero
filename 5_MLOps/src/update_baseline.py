"""Safe baseline update plan."""

from __future__ import annotations

import argparse
import json

from .config import load_config, write_metadata


def baseline_update_plan(execute: bool = False) -> dict[str, object]:
    config = load_config(validate=False)
    if execute and not config.enable_baseline_update:
        raise ValueError("Baseline update is disabled. Set ENABLE_BASELINE_UPDATE=true after evidence review.")
    payload = {
        "action": "baseline_update",
        "executed": bool(execute and config.enable_baseline_update),
        "safe_default": "No baseline is replaced unless --execute and ENABLE_BASELINE_UPDATE=true are both used.",
        "evidence_required": [
            "Drift is expected and accepted by the business context.",
            "Model quality is still acceptable.",
            "No data ingestion bug is suspected.",
            "Reviewer approval is recorded.",
        ],
        "current_statistics_s3_uri": config.statistics_s3_uri,
        "current_constraints_s3_uri": config.constraints_s3_uri,
    }
    write_metadata(config, "baseline_update_plan", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(baseline_update_plan(execute=args.execute), indent=2))


if __name__ == "__main__":
    main()
