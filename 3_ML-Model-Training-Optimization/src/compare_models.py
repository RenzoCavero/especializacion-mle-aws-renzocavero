from __future__ import annotations

import json
import logging
from pathlib import Path

from src.aws_clients import put_json_s3, put_text_s3
from src.config import get_config, s3_join
from src.logging_utils import configure_logging
from src.state import load_state, update_state


LOGGER = logging.getLogger(__name__)


def read_metrics(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("metrics", data)


def metric_value(metrics: dict, name: str) -> float:
    value = metrics.get(name)
    if isinstance(value, dict):
        return float(value.get("value", 0.0))
    return float(value or 0.0)


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    state = load_state()
    baseline_path = state.get("baseline_metrics_local_path")
    optimized_path = state.get("optimized_metrics_local_path")
    if not baseline_path or not Path(baseline_path).exists():
        raise FileNotFoundError("Baseline metrics missing. Run make evaluate-baseline first.")
    if not optimized_path or not Path(optimized_path).exists():
        raise FileNotFoundError("Optimized metrics missing. Run make evaluate-best first.")

    baseline_metrics = read_metrics(baseline_path)
    optimized_metrics = read_metrics(optimized_path)
    baseline_f1 = metric_value(baseline_metrics, "f1")
    optimized_f1 = metric_value(optimized_metrics, "f1")
    selected = "optimized" if optimized_f1 >= baseline_f1 else "baseline"
    selected_artifact = (
        state.get("best_model_artifact_s3_uri") if selected == "optimized" else state.get("baseline_model_artifact_s3_uri")
    )
    selected_metrics_s3 = (
        state.get("optimized_metrics_s3_uri") if selected == "optimized" else state.get("baseline_metrics_s3_uri")
    )
    selected_metric_value = optimized_f1 if selected == "optimized" else baseline_f1

    comparison = {
        "objective_metric": "f1",
        "selection_rule": "Choose the candidate with the highest F1 score.",
        "baseline": baseline_metrics,
        "optimized": optimized_metrics,
        "selected_model": selected,
        "selected_model_artifact_s3_uri": selected_artifact,
        "selected_metrics_s3_uri": selected_metrics_s3,
        "selected_objective_metric_value": selected_metric_value,
    }
    local_json = config.local_outputs_dir / "model_comparison.json"
    local_md = config.local_outputs_dir / "model_comparison.md"
    local_json.write_text(json.dumps(comparison, indent=2, sort_keys=True), encoding="utf-8")
    local_md.write_text(
        "\n".join(
            [
                "# Baseline vs optimized model comparison",
                "",
                "| Candidate | F1 | Recall | Precision | ROC AUC | Accuracy |",
                "|---|---:|---:|---:|---:|---:|",
                (
                    f"| baseline | {baseline_f1:.4f} | {metric_value(baseline_metrics, 'recall'):.4f} | "
                    f"{metric_value(baseline_metrics, 'precision'):.4f} | {metric_value(baseline_metrics, 'roc_auc'):.4f} | "
                    f"{metric_value(baseline_metrics, 'accuracy'):.4f} |"
                ),
                (
                    f"| optimized | {optimized_f1:.4f} | {metric_value(optimized_metrics, 'recall'):.4f} | "
                    f"{metric_value(optimized_metrics, 'precision'):.4f} | {metric_value(optimized_metrics, 'roc_auc'):.4f} | "
                    f"{metric_value(optimized_metrics, 'accuracy'):.4f} |"
                ),
                "",
                f"Selected model: **{selected}** using F1.",
                "",
                "Accuracy is secondary because churn can be class-imbalanced.",
            ]
        ),
        encoding="utf-8",
    )
    comparison_s3_uri = s3_join(config.s3_bucket_name, "metrics", "model_comparison.json")
    comparison_md_s3_uri = s3_join(config.s3_bucket_name, "reports", "model_comparison.md")
    put_json_s3(config, comparison, comparison_s3_uri)
    put_text_s3(config, local_md.read_text(encoding="utf-8"), comparison_md_s3_uri, content_type="text/markdown")
    update_state(
        selected_model_name=selected,
        selected_model_artifact_s3_uri=selected_artifact,
        selected_metrics_s3_uri=selected_metrics_s3,
        objective_metric_name="f1",
        objective_metric_value=selected_metric_value,
        model_comparison_local_path=str(local_json),
        model_comparison_s3_uri=comparison_s3_uri,
    )
    LOGGER.info("Selected %s model with F1 %.4f", selected, selected_metric_value)


if __name__ == "__main__":
    main()
