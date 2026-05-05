"""Evaluate the local fraud scoring model on holdout data."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import (
    EVALUATION_METRICS_PATH,
    EVALUATION_REPORT_PATH,
    MODEL_PATH,
    TARGET_COLUMN,
    TEST_DATA_PATH,
    ensure_directories,
    project_relative,
    require_file,
)
from src.metrics import binary_classification_metrics
from src.modeling import load_model_bundle, predict_proba, save_json, utc_now_iso


def render_evaluation_report(payload: dict[str, Any]) -> str:
    metrics = payload["metrics"]
    confusion = metrics["confusion_matrix"]
    return "\n".join(
        [
            "# Evaluation Report",
            "",
            f"Created at: `{payload['created_at']}`",
            f"Model version: `{payload['model_version']}`",
            f"Dataset: `{payload['dataset_path']}`",
            "",
            "## Metrics",
            "",
            f"- Threshold: `{metrics['threshold']:.3f}`",
            f"- Accuracy: `{metrics['accuracy']:.4f}`",
            f"- Precision: `{metrics['precision']:.4f}`",
            f"- Recall: `{metrics['recall']:.4f}`",
            f"- F1-score: `{metrics['f1']:.4f}`",
            f"- ROC AUC: `{metrics['roc_auc']:.4f}`" if metrics["roc_auc"] is not None else "- ROC AUC: `n/a`",
            f"- PR AUC: `{metrics['pr_auc']:.4f}`" if metrics["pr_auc"] is not None else "- PR AUC: `n/a`",
            "",
            "## Confusion Matrix",
            "",
            "| Metric | Count |",
            "|---|---:|",
            f"| True positive | {confusion['true_positive']} |",
            f"| False positive | {confusion['false_positive']} |",
            f"| True negative | {confusion['true_negative']} |",
            f"| False negative | {confusion['false_negative']} |",
            "",
            "## AWS Mapping",
            "",
            "This local evaluation step mirrors a SageMaker Experiments or Pipeline evaluation step.",
        ]
    )


def evaluate_model(
    test_path: Path = TEST_DATA_PATH,
    model_path: Path = MODEL_PATH,
    metrics_path: Path = EVALUATION_METRICS_PATH,
    report_path: Path = EVALUATION_REPORT_PATH,
) -> dict[str, Any]:
    ensure_directories()
    require_file(test_path, "Run `make prepare` first.")
    require_file(model_path, "Run `make train` first.")

    test_df = pd.read_csv(test_path)
    if TARGET_COLUMN not in test_df.columns:
        raise ValueError(f"Evaluation data must include target column `{TARGET_COLUMN}`.")

    bundle = load_model_bundle(model_path)
    probabilities = predict_proba(bundle, test_df)
    threshold = float(bundle["threshold"])
    metrics = binary_classification_metrics(test_df[TARGET_COLUMN].to_numpy(dtype=int), probabilities, threshold)

    payload = {
        "created_at": utc_now_iso(),
        "dataset_path": project_relative(test_path),
        "model_path": project_relative(model_path),
        "model_version": bundle["model_version"],
        "metrics": metrics,
        "aws_equivalent": "SageMaker Experiments / SageMaker Pipeline Evaluation Step",
    }
    save_json(metrics_path, payload)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_evaluation_report(payload), encoding="utf-8")

    print(f"[evaluate] wrote {metrics_path}")
    print(f"[evaluate] f1={metrics['f1']:.4f} recall={metrics['recall']:.4f} pr_auc={metrics['pr_auc']:.4f}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the fraud scoring model.")
    parser.add_argument("--test-path", default=str(TEST_DATA_PATH))
    parser.add_argument("--model-path", default=str(MODEL_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evaluate_model(test_path=Path(args.test_path), model_path=Path(args.model_path))


if __name__ == "__main__":
    main()
