"""Start and monitor the AWS Glue processing job."""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from typing import Dict

from src.aws_clients import client, get_bucket_name, get_glue_database_name, get_glue_job_name
from src.config import get_settings
from src.package_job_assets import upload_job_assets


TERMINAL_STATES = {"SUCCEEDED", "FAILED", "STOPPED", "TIMEOUT", "ERROR", "EXPIRED"}


def start_processing_job(steps: str = "all", wait: bool = True, poll_seconds: int = 20) -> str:
    settings = get_settings()
    bucket = get_bucket_name(settings)
    database = get_glue_database_name(settings)
    job_name = get_glue_job_name(settings)
    upload_job_assets(bucket)

    glue = client("glue", settings)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    arguments: Dict[str, str] = {
        "--bucket-name": bucket,
        "--database-name": database,
        "--resource-prefix": settings.resource_prefix,
        "--pipeline-steps": steps,
        "--run-id": run_id,
    }
    response = glue.start_job_run(JobName=job_name, Arguments=arguments)
    job_run_id = response["JobRunId"]
    print(f"Started Glue job {job_name} run {job_run_id} with steps={steps}")

    if not wait:
        return job_run_id

    while True:
        run = glue.get_job_run(JobName=job_name, RunId=job_run_id, PredecessorsIncluded=False)["JobRun"]
        state = run["JobRunState"]
        print(f"Glue job state: {state}")
        if state in TERMINAL_STATES:
            if state != "SUCCEEDED":
                raise RuntimeError(f"Glue job failed with state={state}: {run.get('ErrorMessage', '')}")
            return job_run_id
        time.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AWS Glue data preparation job.")
    parser.add_argument("--steps", default="all", help="Comma-separated steps or 'all'.")
    parser.add_argument("--no-wait", action="store_true", help="Start the job and return immediately.")
    parser.add_argument("--poll-seconds", type=int, default=20)
    args = parser.parse_args()
    start_processing_job(steps=args.steps, wait=not args.no_wait, poll_seconds=args.poll_seconds)


if __name__ == "__main__":
    main()

