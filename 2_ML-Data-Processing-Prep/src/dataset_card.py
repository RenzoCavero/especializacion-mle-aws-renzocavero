"""Dataset card generation for prepared ML datasets."""

from __future__ import annotations

from typing import Dict

from src.data_utils import utc_now_iso
from src.schemas import FEATURE_COLUMNS


def build_dataset_card(
    bucket_name: str,
    profile: Dict[str, object],
    quality: Dict[str, object],
    training_rows: int,
    inference_rows: int,
) -> Dict[str, object]:
    return {
        "generated_at": utc_now_iso(),
        "dataset_name": "fraud_risk_prepared_features",
        "business_problem": "Detect possible fraudulent transactions or score transaction risk.",
        "intended_use": [
            "Training binary classification models in future labs.",
            "Batch inference with the same feature contract.",
            "Baseline for future drift monitoring.",
        ],
        "not_intended_use": [
            "Production decisions without model validation.",
            "Use with real PII without privacy, compliance and security review.",
        ],
        "data_source": "Synthetic customer and transaction data generated for the lab.",
        "s3_outputs": {
            "training_dataset": f"s3://{bucket_name}/features/training_dataset.csv",
            "inference_dataset": f"s3://{bucket_name}/inference/inference_dataset.csv",
            "profiles": f"s3://{bucket_name}/profiles/profile.json",
            "quality": f"s3://{bucket_name}/quality/quality_report.json",
            "lineage": f"s3://{bucket_name}/lineage/lineage.json",
        },
        "row_counts": {
            "training_dataset": training_rows,
            "inference_dataset": inference_rows,
        },
        "feature_columns": FEATURE_COLUMNS,
        "target": "is_fraud",
        "quality_summary": quality.get("summary", {}),
        "profile_summary": {
            name: details.get("row_count")
            for name, details in profile.get("datasets", {}).items()  # type: ignore[union-attr]
            if isinstance(details, dict)
        },
        "limitations": [
            "Synthetic data does not represent real fraud prevalence.",
            "Feature Store online is intentionally not enabled to control cost.",
            "Quality rules are educational and should be expanded for production.",
        ],
        "security": [
            "No real PII is used.",
            "S3 bucket is private and encrypted by default.",
            "Processing uses an IAM role scoped to lab resources.",
        ],
    }


def dataset_card_to_markdown(card: Dict[str, object]) -> str:
    lines = [
        "# Dataset Card",
        "",
        f"Generated at: `{card['generated_at']}`",
        "",
        f"Dataset: `{card['dataset_name']}`",
        "",
        "## Business Problem",
        "",
        str(card["business_problem"]),
        "",
        "## Intended Use",
        "",
    ]
    lines.extend([f"- {item}" for item in card["intended_use"]])  # type: ignore[index]
    lines.extend(["", "## Not Intended Use", ""])
    lines.extend([f"- {item}" for item in card["not_intended_use"]])  # type: ignore[index]
    lines.extend(["", "## Outputs", ""])
    for name, uri in card["s3_outputs"].items():  # type: ignore[union-attr]
        lines.append(f"- {name}: `{uri}`")
    lines.extend(["", "## Row Counts", ""])
    for name, count in card["row_counts"].items():  # type: ignore[union-attr]
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Features", ""])
    lines.extend([f"- `{column}`" for column in card["feature_columns"]])  # type: ignore[index]
    lines.extend(["", "## Target", "", f"`{card['target']}`"])
    lines.extend(["", "## Quality Summary", "", "```json", str(card["quality_summary"]), "```"])
    lines.extend(["", "## Limitations", ""])
    lines.extend([f"- {item}" for item in card["limitations"]])  # type: ignore[index]
    lines.extend(["", "## Security", ""])
    lines.extend([f"- {item}" for item in card["security"]])  # type: ignore[index]
    lines.append("")
    return "\n".join(lines)
