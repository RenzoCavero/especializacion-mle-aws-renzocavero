from __future__ import annotations

import json
import logging

from src.aws_clients import put_text_s3
from src.config import get_config, s3_join
from src.logging_utils import configure_logging
from src.state import load_state


LOGGER = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    state = load_state()
    comparison = {}
    comparison_path = state.get("model_comparison_local_path")
    if comparison_path:
        comparison = json.loads(open(comparison_path, encoding="utf-8").read())

    lines = [
        "# Training report - Lab 03",
        "",
        f"- Project: {config.project_name}",
        f"- Environment: {config.environment}",
        f"- Feature Group: {config.feature_group_name}",
        f"- Offline Store: {config.offline_store_s3_uri}",
        f"- Processing feature source: {state.get('feature_data_source', config.feature_data_source)}",
        f"- Processing Job: {state.get('processing_job_name')}",
        f"- Baseline Training Job: {state.get('baseline_training_job_name')}",
        f"- HPO Job: {state.get('hpo_job_name')}",
        f"- Best Training Job: {state.get('best_training_job_name')}",
        f"- Selected Model: {state.get('selected_model_name')}",
        f"- Objective Metric: {state.get('objective_metric_name', 'f1')}={state.get('objective_metric_value')}",
        f"- Model Package ARN: {state.get('model_package_arn')}",
        "",
        "## Model comparison",
        "",
        "```json",
        json.dumps(comparison, indent=2, sort_keys=True),
        "```",
        "",
        "## Continuity",
        "",
        "- Batch inference should use the Offline Store or processed datasets derived from it.",
        "- Real-time inference should lookup features in the Online Store by customer_id.",
        "- churn_label is target-only and must never be sent as inference input.",
    ]
    local_path = config.local_outputs_dir / "training_report.md"
    local_path.write_text("\n".join(lines), encoding="utf-8")
    s3_uri = s3_join(config.s3_bucket_name, "reports", "training_report.md")
    put_text_s3(config, local_path.read_text(encoding="utf-8"), s3_uri, content_type="text/markdown")
    LOGGER.info("Training report written to %s and %s", local_path, s3_uri)


if __name__ == "__main__":
    main()
