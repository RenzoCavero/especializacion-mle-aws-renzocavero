from __future__ import annotations

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
    lines = [
        "# Model card - Churn model candidate",
        "",
        "## Intended use",
        "",
        "Educational churn-risk model for AWS ML training and optimization. It is not approved for production use.",
        "",
        "## Model details",
        "",
        f"- Model package group: {config.model_package_group_name}",
        f"- Model package ARN: {state.get('model_package_arn')}",
        f"- Approval status: {state.get('model_approval_status', 'PendingManualApproval')}",
        f"- Model artifact: {state.get('selected_model_artifact_s3_uri')}",
        f"- Objective metric: {state.get('objective_metric_name', 'f1')}={state.get('objective_metric_value')}",
        "",
        "## Data and features",
        "",
        f"- Feature Group: {config.feature_group_name}",
        "- Record identifier: customer_id",
        "- Event time feature: event_time",
        "- Target column: churn_label",
        "- Training source: Feature Store Offline Store or processed snapshot derived from validated Feature Store records.",
        "- Real-time source: Feature Store Online Store lookup by customer_id.",
        "",
        "## Metrics",
        "",
        "F1, recall, precision and ROC AUC are the primary metrics. Accuracy is secondary because churn may be imbalanced.",
        "",
        "## Limitations",
        "",
        "- Dataset is synthetic.",
        "- HPO is intentionally small to control cost.",
        "- No persistent endpoint is created in this lab.",
        "- Human approval is required before production promotion.",
    ]
    local_path = config.local_outputs_dir / "model_card.md"
    local_path.write_text("\n".join(lines), encoding="utf-8")
    s3_uri = s3_join(config.s3_bucket_name, "reports", "model_card.md")
    put_text_s3(config, local_path.read_text(encoding="utf-8"), s3_uri, content_type="text/markdown")
    LOGGER.info("Model card written to %s and %s", local_path, s3_uri)


if __name__ == "__main__":
    main()
