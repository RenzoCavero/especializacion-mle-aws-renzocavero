"""Safe rollback plan for the lab endpoint."""

from __future__ import annotations

import argparse
import json

from .config import load_config, write_metadata


def rollback_plan(execute: bool = False) -> dict[str, object]:
    config = load_config(validate=False)
    if execute and not config.enable_rollback_execution:
        raise ValueError("Rollback execution is disabled. Set ENABLE_ROLLBACK_EXECUTION=true after review.")
    payload = {
        "action": "rollback",
        "executed": bool(execute and config.enable_rollback_execution),
        "endpoint_name": config.endpoint_name,
        "safe_default": "No endpoint traffic is changed unless --execute and ENABLE_ROLLBACK_EXECUTION=true are both used.",
        "procedure": [
            "Find previous Approved model package in Model Registry.",
            "Create a new SageMaker model and endpoint config.",
            "Update endpoint to the previous approved model.",
            "Run smoke tests and monitor CloudWatch.",
        ],
    }
    write_metadata(config, "rollback_plan", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(rollback_plan(execute=args.execute), indent=2))


if __name__ == "__main__":
    main()

