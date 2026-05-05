"""Generate governance documentation for the local fraud model."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.config import (
    DATA_PROFILE_PATH,
    EVALUATION_METRICS_PATH,
    MODEL_CARD_PATH,
    MODEL_METADATA_PATH,
    MONITORING_REPORT_PATH,
    ensure_directories,
    project_relative,
    require_file,
)
from src.modeling import load_json, save_json, utc_now_iso


def _fmt_metric(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def render_model_card(
    metadata: dict[str, Any],
    evaluation: dict[str, Any],
    profile: dict[str, Any],
    monitoring: dict[str, Any],
) -> str:
    metrics = evaluation["metrics"]
    alerts = monitoring.get("alerts", [])
    alert_lines = [f"- {alert}" for alert in alerts] or ["- No active alerts in the local simulation."]
    chart_paths = monitoring.get("chart_paths", {})
    chart_lines = [
        f"- PSI ranking: `{chart_paths.get('psi_by_feature', 'n/a')}`",
        f"- Alert heatmap: `{chart_paths.get('alert_heatmap', 'n/a')}`",
        f"- Chart directory: `{chart_paths.get('charts_dir', 'n/a')}`",
    ]
    return "\n".join(
        [
            "# Model Card: Fraud Risk Scoring",
            "",
            f"Generated at: `{utc_now_iso()}`",
            f"Model version: `{metadata['model_version']}`",
            f"Model type: `{metadata['model_type']}`",
            "",
            "## Intended Use",
            "",
            "Estimate fraud probability for synthetic card-like transactions and produce an operational decision: approve, review or block.",
            "This is an educational local lab and must not be used for real customer decisions.",
            "",
            "## Business Context",
            "",
            "The business goal is to reduce fraud losses while minimizing friction for legitimate customers.",
            "The ML framing is binary classification / risk scoring over transaction features.",
            "",
            "## Training Data",
            "",
            f"- Source: `{profile['source_path']}`",
            f"- Raw rows: `{profile['raw_rows']}`",
            f"- Train rows: `{profile['train_rows']}`",
            f"- Test rows: `{profile['test_rows']}`",
            f"- Raw fraud rate: `{profile['fraud_rate_raw']:.4f}`",
            "- Data origin: synthetic generator, no real personal data.",
            "",
            "## Evaluation",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Accuracy | {_fmt_metric(metrics['accuracy'])} |",
            f"| Precision | {_fmt_metric(metrics['precision'])} |",
            f"| Recall | {_fmt_metric(metrics['recall'])} |",
            f"| F1-score | {_fmt_metric(metrics['f1'])} |",
            f"| ROC AUC | {_fmt_metric(metrics['roc_auc'])} |",
            f"| PR AUC | {_fmt_metric(metrics['pr_auc'])} |",
            "",
            "Accuracy is not the primary metric because fraud data is imbalanced. Recall, precision, F1 and PR AUC are more relevant.",
            "",
            "## Monitoring Summary",
            "",
            f"- Average fraud probability in batch scoring: `{monitoring['average_fraud_probability']:.4f}`",
            f"- Review/block rate: `{monitoring['review_or_block_rate']:.4f}`",
            "",
            "### Alerts",
            "",
            *alert_lines,
            "",
            "### Monitoring Charts",
            "",
            *chart_lines,
            "",
            "## Limitations",
            "",
            "- Dataset is synthetic and intentionally simplified.",
            "- Features are representative but not exhaustive.",
            "- The model is a lightweight NumPy implementation for teaching, not a production-grade fraud engine.",
            "- Thresholds are examples and should be calibrated with business cost matrices in real projects.",
            "",
            "## Ethical And Governance Notes",
            "",
            "- Do not use this model for real credit, fraud, employment or eligibility decisions.",
            "- Avoid storing credentials or personal data in the repository.",
            "- In AWS, align this documentation with SageMaker Model Cards, Model Registry approval and audit trails.",
            "",
            "## Local To AWS Mapping",
            "",
            "| Local artifact | AWS conceptual equivalent |",
            "|---|---|",
            "| `data/raw/` | Amazon S3 raw zone |",
            "| `data/processed/` | Amazon S3 curated zone |",
            "| `src/train.py` | SageMaker Training Job |",
            "| `src/evaluate.py` | SageMaker Pipeline Evaluation Step |",
            "| `artifacts/model/model.joblib` | SageMaker model artifact |",
            "| `src/batch_inference.py` | SageMaker Batch Transform |",
            "| FastAPI `/predict` | SageMaker real-time endpoint |",
            "| `src/monitor.py` | SageMaker Model Monitor + CloudWatch |",
            "| this model card | SageMaker Model Cards / governance docs |",
        ]
    )


def generate_model_card(
    metadata_path: Path = MODEL_METADATA_PATH,
    evaluation_path: Path = EVALUATION_METRICS_PATH,
    profile_path: Path = DATA_PROFILE_PATH,
    monitoring_path: Path = MONITORING_REPORT_PATH,
    output_path: Path = MODEL_CARD_PATH,
) -> dict[str, Any]:
    ensure_directories()
    require_file(metadata_path, "Run `make train` first.")
    require_file(evaluation_path, "Run `make evaluate` first.")
    require_file(profile_path, "Run `make prepare` first.")
    require_file(monitoring_path, "Run `make monitor` first.")

    metadata = load_json(metadata_path)
    evaluation = load_json(evaluation_path)
    profile = load_json(profile_path)
    monitoring = load_json(monitoring_path)

    content = render_model_card(metadata, evaluation, profile, monitoring)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    summary = {
        "created_at": utc_now_iso(),
        "model_card_path": project_relative(output_path),
        "model_version": metadata["model_version"],
        "approval_status": "local-demo-not-approved-for-production",
        "aws_equivalent": "SageMaker Model Cards / Model Registry documentation",
    }
    save_json(output_path.parent / "governance_summary.json", summary)
    print(f"[model-card] wrote {output_path}")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate model card.")
    parser.add_argument("--output-path", default=str(MODEL_CARD_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_model_card(output_path=Path(args.output_path))


if __name__ == "__main__":
    main()
