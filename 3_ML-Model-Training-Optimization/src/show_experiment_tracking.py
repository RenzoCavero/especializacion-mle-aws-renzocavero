from __future__ import annotations

import json
import logging

from botocore.exceptions import ClientError

from src.aws_clients import client
from src.config import get_config
from src.logging_utils import configure_logging
from src.state import load_state


LOGGER = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    sm = client(config, "sagemaker")
    state = load_state()

    report = {
        "experiment_name": config.experiment_name,
        "tracked_jobs_from_state": {
            "processing_job_name": state.get("processing_job_name"),
            "baseline_training_job_name": state.get("baseline_training_job_name"),
            "hpo_job_name": state.get("hpo_job_name"),
            "best_training_job_name": state.get("best_training_job_name"),
        },
        "trials": [],
    }
    try:
        sm.describe_experiment(ExperimentName=config.experiment_name)
        trials = sm.list_trials(ExperimentName=config.experiment_name, MaxResults=50)
        report["trials"] = trials.get("TrialSummaries", [])
    except ClientError as exc:
        report["warning"] = f"Experiment not found yet or not accessible: {exc.response.get('Error', {}).get('Message')}"

    local_path = config.local_outputs_dir / "experiment_tracking_report.json"
    local_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    LOGGER.info("Experiment tracking report written to %s", local_path)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
