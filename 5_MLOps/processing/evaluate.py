"""Evaluate a trained churn model and write SageMaker-compatible metrics."""

from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score


LABEL_COLUMN = "churned"


def evaluate(model_path: Path, test_data: Path, output_path: Path) -> dict[str, float]:
    if model_path.is_dir():
        direct = model_path / "model.joblib"
        archive = model_path / "model.tar.gz"
        if direct.exists():
            model_path = direct
        elif archive.exists():
            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(model_path)
            model_path = direct
    model = joblib.load(model_path)
    frame = pd.read_csv(test_data)
    y_true = frame[LABEL_COLUMN]
    features = frame.drop(columns=[LABEL_COLUMN])
    predictions = model.predict(features)

    if hasattr(model, "predict_proba"):
        scores = model.predict_proba(features)[:, 1]
    else:
        scores = predictions

    metrics = {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "f1": float(f1_score(y_true, predictions)),
        "auc": float(roc_auc_score(y_true, scores)),
    }
    payload = {
        "binary_classification_metrics": {
            "accuracy": {"value": metrics["accuracy"], "standard_deviation": "NaN"},
            "f1": {"value": metrics["f1"], "standard_deviation": "NaN"},
            "auc": {"value": metrics["auc"], "standard_deviation": "NaN"},
        },
        "metrics": metrics,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", default="/opt/ml/processing/model/model.joblib")
    parser.add_argument("--test-data", default="/opt/ml/processing/test/test.csv")
    parser.add_argument("--output-path", default="/opt/ml/processing/evaluation/evaluation.json")
    args = parser.parse_args()
    metrics = evaluate(Path(args.model_path), Path(args.test_data), Path(args.output_path))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
