from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, "/opt/ml/processing/lib")

from utils import (
    TARGET_COLUMN,
    ensure_dir,
    evaluate_predictions,
    extract_model,
    load_model_bundle,
    write_json,
)


def find_csv(path: Path) -> Path:
    if path.is_file():
        return path
    candidates = sorted(path.glob("*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No CSV file found under {path}")
    return candidates[0]


def find_model_tar(path: Path) -> Path:
    if path.is_file() and path.name.endswith(".tar.gz"):
        return path
    candidates = sorted(path.glob("*.tar.gz"))
    if not candidates:
        raise FileNotFoundError(f"No model.tar.gz file found under {path}")
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a SageMaker model artifact with held-out data.")
    parser.add_argument("--test-data", default="/opt/ml/processing/test")
    parser.add_argument("--model-artifact", default="/opt/ml/processing/model")
    parser.add_argument("--evaluation-output", default="/opt/ml/processing/evaluation")
    parser.add_argument("--reports-output", default="/opt/ml/processing/reports")
    parser.add_argument("--model-name", default="candidate")
    args = parser.parse_args()

    test_path = find_csv(Path(args.test_data))
    model_tar = find_model_tar(Path(args.model_artifact))
    evaluation_dir = ensure_dir(args.evaluation_output)
    reports_dir = ensure_dir(args.reports_output)
    extracted_model_dir = extract_model(model_tar, evaluation_dir / "model")
    bundle = load_model_bundle(extracted_model_dir)

    df = pd.read_csv(test_path)
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Test dataset must include {TARGET_COLUMN}")
    feature_columns = bundle["feature_columns"]
    missing = [column for column in feature_columns if column not in df.columns]
    if missing:
        raise ValueError(f"Test dataset is missing model columns: {missing}")

    X = df[feature_columns]
    y_true = df[TARGET_COLUMN].astype(int)
    model = bundle["model"]
    y_pred = model.predict(X)
    y_score = model.predict_proba(X)[:, 1] if hasattr(model, "predict_proba") else y_pred
    metrics = evaluate_predictions(y_true, y_pred, y_score)

    output = {
        "model_name": args.model_name,
        "metrics": metrics,
        "classification_metrics": {
            "f1": {"value": metrics["f1"]},
            "precision": {"value": metrics["precision"]},
            "recall": {"value": metrics["recall"]},
            "roc_auc": {"value": metrics["roc_auc"]},
            "accuracy": {"value": metrics["accuracy"]},
        },
        "test_rows": int(len(df)),
        "feature_columns": feature_columns,
    }
    write_json(output, evaluation_dir / "evaluation_metrics.json")
    write_json(output, evaluation_dir / "evaluation.json")

    report = [
        f"# Evaluation report: {args.model_name}",
        "",
        f"- Test rows: {len(df)}",
        f"- F1: {metrics['f1']:.4f}",
        f"- Recall: {metrics['recall']:.4f}",
        f"- Precision: {metrics['precision']:.4f}",
        f"- ROC AUC: {metrics['roc_auc']:.4f}",
        f"- Accuracy: {metrics['accuracy']:.4f}",
        f"- Confusion matrix: {metrics['confusion_matrix']}",
        "",
        "Accuracy is reported only as a secondary metric. Churn selection should prioritize F1, recall and AUC.",
    ]
    (reports_dir / f"{args.model_name}_evaluation_report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"evaluation:f1={metrics['f1']:.6f}")
    print(f"evaluation:recall={metrics['recall']:.6f}")
    print(f"evaluation:precision={metrics['precision']:.6f}")
    print(f"evaluation:roc_auc={metrics['roc_auc']:.6f}")


if __name__ == "__main__":
    main()
