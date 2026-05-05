"""Run local batch inference for fraud scoring."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import (
    BATCH_INPUT_PATH,
    BATCH_PREDICTIONS_PATH,
    BATCH_SUMMARY_PATH,
    DECISION_BLOCK_THRESHOLD,
    DECISION_REVIEW_THRESHOLD,
    ID_COLUMNS,
    MODEL_PATH,
    ensure_directories,
    project_relative,
    require_file,
)
from src.data_preparation import ensure_feature_frame
from src.modeling import decision_from_probability, load_model_bundle, predict_proba, save_json, utc_now_iso


def run_batch_inference(
    input_path: Path = BATCH_INPUT_PATH,
    model_path: Path = MODEL_PATH,
    output_path: Path = BATCH_PREDICTIONS_PATH,
    summary_path: Path = BATCH_SUMMARY_PATH,
) -> dict[str, Any]:
    ensure_directories()
    require_file(input_path, "Run `make prepare` first.")
    require_file(model_path, "Run `make train` first.")

    input_df = pd.read_csv(input_path)
    feature_df = ensure_feature_frame(input_df)
    bundle = load_model_bundle(model_path)
    probabilities = predict_proba(bundle, feature_df)
    review_threshold = float(bundle.get("threshold", DECISION_REVIEW_THRESHOLD))
    decisions = [
        decision_from_probability(
            float(probability),
            review_threshold=review_threshold,
            block_threshold=DECISION_BLOCK_THRESHOLD,
        )
        for probability in probabilities
    ]

    output_columns = [column for column in ID_COLUMNS if column in feature_df.columns]
    predictions = feature_df[output_columns].copy()
    predictions["fraud_probability"] = probabilities.round(6)
    predictions["risk_decision"] = decisions
    predictions["model_version"] = bundle["model_version"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output_path, index=False)

    summary = {
        "created_at": utc_now_iso(),
        "input_path": project_relative(input_path),
        "output_path": project_relative(output_path),
        "model_version": bundle["model_version"],
        "rows": int(len(predictions)),
        "average_fraud_probability": float(predictions["fraud_probability"].mean()),
        "review_threshold": review_threshold,
        "block_threshold": DECISION_BLOCK_THRESHOLD,
        "decision_counts": {key: int(value) for key, value in predictions["risk_decision"].value_counts().to_dict().items()},
        "aws_equivalent": "SageMaker Batch Transform",
    }
    save_json(summary_path, summary)

    print(f"[batch] wrote {output_path} rows={len(predictions)}")
    print(f"[batch] decisions={summary['decision_counts']}")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run batch inference.")
    parser.add_argument("--input-path", default=str(BATCH_INPUT_PATH))
    parser.add_argument("--model-path", default=str(MODEL_PATH))
    parser.add_argument("--output-path", default=str(BATCH_PREDICTIONS_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_batch_inference(
        input_path=Path(args.input_path),
        model_path=Path(args.model_path),
        output_path=Path(args.output_path),
    )


if __name__ == "__main__":
    main()
