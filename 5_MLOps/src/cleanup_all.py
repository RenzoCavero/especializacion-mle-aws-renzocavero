"""Run safe cleanup for lab resources."""

from __future__ import annotations

import argparse
import json

from .cleanup_endpoint import cleanup_endpoint
from .cleanup_feedback_loop import cleanup_feedback_loop
from .cleanup_local_outputs import cleanup_local_outputs
from .cleanup_monitoring import cleanup_monitoring
from .cleanup_s3_artifacts import cleanup_s3_artifacts
from .cleanup_sagemaker_resources import cleanup_sagemaker_resources
from .config import load_config, write_metadata


def cleanup_all(
    include_external: bool = False,
    delete_s3_outputs: bool = True,
    delete_local_outputs: bool = False,
) -> dict[str, object]:
    config = load_config(validate=True)
    payload = {
        "endpoint": cleanup_endpoint(include_external=include_external),
        "monitoring": cleanup_monitoring(delete_s3_outputs=delete_s3_outputs),
        "feedback_loop": cleanup_feedback_loop(),
        "sagemaker_resources": cleanup_sagemaker_resources(include_external=include_external),
        "s3_artifacts": cleanup_s3_artifacts(execute=delete_s3_outputs),
        "local_outputs": cleanup_local_outputs(execute=delete_local_outputs),
        "s3_outputs_deleted": delete_s3_outputs,
        "s3_note": (
            "Cleanup deletes objects under the exact lab S3 prefix by default. "
            "Use --retain-s3-outputs to keep S3 evidence."
        ),
        "local_outputs_note": (
            "Local evidence files are retained by default. Run "
            "`python -m src.cleanup_local_outputs --execute` or "
            "`python -m src.cleanup_all --delete-local-outputs` to delete generated local lab files."
        ),
    }
    write_metadata(config, "cleanup_all", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-external", action="store_true")
    parser.add_argument("--delete-s3-outputs", action="store_true", help="Deprecated: S3 lab artifacts are deleted by default.")
    parser.add_argument("--retain-s3-outputs", action="store_true")
    parser.add_argument("--delete-local-outputs", action="store_true")
    args = parser.parse_args()
    delete_s3_outputs = args.delete_s3_outputs or not args.retain_s3_outputs
    print(
        json.dumps(
            cleanup_all(args.include_external, delete_s3_outputs, args.delete_local_outputs),
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
