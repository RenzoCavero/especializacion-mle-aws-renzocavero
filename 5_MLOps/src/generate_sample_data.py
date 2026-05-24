"""Generate synthetic churn data for standalone_mode."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .aws_clients import create_clients
from .config import LabConfig, load_config, write_metadata


FEATURE_COLUMNS = [
    "age",
    "monthly_spend",
    "support_tickets",
    "tenure_months",
    "late_payments",
    "plan_type",
    "region",
]
LABEL_COLUMN = "churned"


def _make_frame(n_rows: int, seed: int, drift: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    age = rng.normal(38 if not drift else 46, 11, n_rows).clip(18, 78)
    monthly_spend = rng.normal(70 if not drift else 105, 22, n_rows).clip(15, 240)
    support_tickets = rng.poisson(1.1 if not drift else 3.0, n_rows).clip(0, 10)
    tenure_months = rng.gamma(4 if not drift else 2, 8, n_rows).clip(1, 96)
    late_payments = rng.poisson(0.35 if not drift else 1.2, n_rows).clip(0, 8)
    plan_type = rng.choice(["basic", "standard", "premium"], n_rows, p=[0.45, 0.40, 0.15] if not drift else [0.65, 0.25, 0.10])
    region = rng.choice(["north", "south", "east", "west"], n_rows, p=[0.25, 0.25, 0.25, 0.25] if not drift else [0.10, 0.50, 0.20, 0.20])

    plan_risk = np.select(
        [plan_type == "basic", plan_type == "standard", plan_type == "premium"],
        [1.10, 0.00, -1.00],
        default=0.0,
    )
    region_risk = np.select(
        [region == "south", region == "west"],
        [0.55 if drift else 0.40, 0.20],
        default=0.0,
    )
    raw_risk = (
        0.050 * (age - 38)
        + 0.040 * (monthly_spend - 70)
        + 1.20 * support_tickets
        - 0.080 * tenure_months
        + 1.50 * late_payments
        + plan_risk
        + region_risk
    )
    logits = -0.80 + 1.50 * raw_risk
    probability = 1 / (1 + np.exp(-logits))
    churned = rng.binomial(1, probability)

    frame = pd.DataFrame(
        {
            "record_id": [f"{'drift' if drift else 'normal'}-{seed}-{i:05d}" for i in range(n_rows)],
            "age": age.round(1),
            "monthly_spend": monthly_spend.round(2),
            "support_tickets": support_tickets.astype(int),
            "tenure_months": tenure_months.round(1),
            "late_payments": late_payments.astype(int),
            "plan_type": plan_type,
            "region": region,
            LABEL_COLUMN: churned.astype(int),
        }
    )
    return frame


def write_jsonl(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in frame.to_dict(orient="records"):
            row.pop(LABEL_COLUMN, None)
            handle.write(json.dumps(row) + "\n")


def write_ground_truth_jsonl(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in frame[["record_id", LABEL_COLUMN]].to_dict(orient="records"):
            handle.write(json.dumps(row) + "\n")


def generate(config: LabConfig, seed: int = 42, n_rows: int = 1200) -> dict[str, Path]:
    config.ensure_local_dirs()
    normal = _make_frame(n_rows=n_rows, seed=seed, drift=False)
    drift = _make_frame(n_rows=max(300, n_rows // 4), seed=seed + 7, drift=True)

    train_path = config.local_cache_dir / "churn_train.csv"
    baseline_path = config.local_cache_dir / "baseline.csv"
    inference_path = config.local_cache_dir / "inference_normal.jsonl"
    drift_path = config.local_cache_dir / "inference_drift.jsonl"
    inference_ground_truth_path = config.local_cache_dir / "inference_normal_ground_truth.jsonl"
    drift_ground_truth_path = config.local_cache_dir / "inference_drift_ground_truth.jsonl"

    normal.to_csv(train_path, index=False)
    normal.drop(columns=[LABEL_COLUMN]).sample(min(300, len(normal)), random_state=seed).to_csv(baseline_path, index=False)
    write_jsonl(normal.drop(columns=[LABEL_COLUMN]).head(100).assign(**{LABEL_COLUMN: normal[LABEL_COLUMN].head(100)}), inference_path)
    write_jsonl(drift.drop(columns=[LABEL_COLUMN]).head(100).assign(**{LABEL_COLUMN: drift[LABEL_COLUMN].head(100)}), drift_path)
    write_ground_truth_jsonl(normal.head(100), inference_ground_truth_path)
    write_ground_truth_jsonl(drift.head(100), drift_ground_truth_path)

    return {
        "train": train_path,
        "baseline": baseline_path,
        "inference_normal": inference_path,
        "inference_drift": drift_path,
        "inference_normal_ground_truth": inference_ground_truth_path,
        "inference_drift_ground_truth": drift_ground_truth_path,
    }


def upload_file(config: LabConfig, local_path: Path, s3_key: str) -> str:
    config.validate_for_cloud()
    clients = create_clients(config)
    clients.s3.upload_file(str(local_path), config.s3_bucket_name, s3_key)
    return f"s3://{config.s3_bucket_name}/{s3_key}"


def upload_generated_data(config: LabConfig, paths: dict[str, Path]) -> dict[str, str]:
    prefix = f"{config.resource_prefix}/{config.environment}/data/raw"
    return {
        name: upload_file(config, path, f"{prefix}/{path.name}")
        for name, path in paths.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate standalone synthetic churn data.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rows", type=int, default=1200)
    parser.add_argument("--upload", action="store_true", help="Upload generated files to S3.")
    args = parser.parse_args()

    config = load_config(validate=args.upload)
    paths = generate(config, seed=args.seed, n_rows=args.rows)
    uploaded: dict[str, str] = {}
    if args.upload:
        uploaded = upload_generated_data(config, paths)

    metadata = {
        "local_files": {name: str(path) for name, path in paths.items()},
        "s3_files": uploaded,
        "feature_columns": FEATURE_COLUMNS,
        "label_column": LABEL_COLUMN,
        "records": args.rows,
        "drift_records": max(300, args.rows // 4),
    }
    write_metadata(config, "data_generation", metadata)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
