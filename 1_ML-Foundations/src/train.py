"""Train a local fraud scoring model."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import (
    MODEL_METADATA_PATH,
    MODEL_PATH,
    MODEL_VERSION,
    TARGET_COLUMN,
    TRAINING_METRICS_PATH,
    TRAIN_DATA_PATH,
    ensure_directories,
    project_relative,
    require_file,
)
from src.metrics import binary_classification_metrics, choose_threshold
from src.modeling import (
    fit_preprocessor,
    predict_proba_matrix,
    save_json,
    save_model_bundle,
    train_logistic_regression,
    transform_features,
    utc_now_iso,
)


DEFAULT_MODEL_PARAMS = {
    "learning_rate": 0.06,
    "epochs": 900,
    "l2": 0.01,
    "seed": 42,
}


def train_model(
    train_path: Path = TRAIN_DATA_PATH,
    model_path: Path = MODEL_PATH,
    metrics_path: Path = TRAINING_METRICS_PATH,
    metadata_path: Path = MODEL_METADATA_PATH,
    model_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_directories()
    require_file(train_path, "Run `make prepare` or `python -m src.data_preparation` first.")
    params = dict(DEFAULT_MODEL_PARAMS)
    if model_params:
        params.update(model_params)

    train_df = pd.read_csv(train_path)
    if TARGET_COLUMN not in train_df.columns:
        raise ValueError(f"Training data must include target column `{TARGET_COLUMN}`.")

    preprocessor = fit_preprocessor(train_df)
    x_train = transform_features(train_df, preprocessor)
    y_train = train_df[TARGET_COLUMN].to_numpy(dtype=int)

    trained = train_logistic_regression(x_train, y_train, **params)
    probabilities = predict_proba_matrix(x_train, trained["weights"], trained["bias"])
    threshold, training_metrics = choose_threshold(y_train, probabilities, min_recall=0.70)
    training_metrics = binary_classification_metrics(y_train, probabilities, threshold)

    bundle = {
        "model_version": MODEL_VERSION,
        "created_at": utc_now_iso(),
        "preprocessor": preprocessor,
        "weights": trained["weights"],
        "bias": trained["bias"],
        "threshold": float(threshold),
        "training_metrics": training_metrics,
        "training_details": {
            key: value for key, value in trained.items() if key != "weights"
        },
    }
    save_model_bundle(model_path, bundle)

    metrics_payload = {
        "created_at": utc_now_iso(),
        "dataset_path": project_relative(train_path),
        "model_path": project_relative(model_path),
        "model_version": MODEL_VERSION,
        "model_params": params,
        "selected_threshold": float(threshold),
        "metrics": training_metrics,
    }
    save_json(metrics_path, metrics_payload)

    metadata = {
        "created_at": utc_now_iso(),
        "model_version": MODEL_VERSION,
        "model_type": "weighted_logistic_regression_numpy",
        "artifact_path": project_relative(model_path),
        "threshold": float(threshold),
        "training_rows": int(len(train_df)),
        "feature_count": int(len(preprocessor["feature_names"])),
        "feature_names": preprocessor["feature_names"],
        "positive_label_rate": float(train_df[TARGET_COLUMN].mean()),
        "notes": [
            "Local educational model inspired by SageMaker Training Jobs.",
            "No AWS resources are created by this step.",
        ],
    }
    save_json(metadata_path, metadata)

    print(f"[train] wrote {model_path}")
    print(f"[train] threshold={threshold:.3f} train_f1={training_metrics['f1']:.4f}")
    return metrics_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the fraud scoring model.")
    parser.add_argument("--train-path", default=str(TRAIN_DATA_PATH))
    parser.add_argument("--model-path", default=str(MODEL_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train_model(train_path=Path(args.train_path), model_path=Path(args.model_path))


if __name__ == "__main__":
    main()
