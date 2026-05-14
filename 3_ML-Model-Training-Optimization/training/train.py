from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from utils import load_supervised_dataset


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a churn baseline model with scikit-learn.")
    parser.add_argument("-C", "--C", dest="C", type=float, default=1.0)
    parser.add_argument("--max-iter", type=int, default=250)
    parser.add_argument("--class-weight", default="balanced", choices=["balanced", "none"])
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--train", default=os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train"))
    parser.add_argument("--validation", default=os.environ.get("SM_CHANNEL_VALIDATION", "/opt/ml/input/data/validation"))
    parser.add_argument("--model-dir", default=os.environ.get("SM_MODEL_DIR", "/opt/ml/model"))
    return parser.parse_args(argv)


def metric_or_zero(metric_fn, y_true, y_pred_or_score) -> float:
    try:
        return float(metric_fn(y_true, y_pred_or_score))
    except ValueError:
        return 0.0


def main() -> None:
    args = parse_args()
    X_train, y_train = load_supervised_dataset(args.train)
    X_validation, y_validation = load_supervised_dataset(args.validation)

    class_weight = None if args.class_weight == "none" else "balanced"
    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    C=args.C,
                    max_iter=args.max_iter,
                    class_weight=class_weight,
                    random_state=args.random_state,
                    solver="lbfgs",
                ),
            ),
        ]
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_validation)
    y_score = model.predict_proba(X_validation)[:, 1]
    metrics = {
        "accuracy": float(accuracy_score(y_validation, y_pred)),
        "precision": float(precision_score(y_validation, y_pred, zero_division=0)),
        "recall": float(recall_score(y_validation, y_pred, zero_division=0)),
        "f1": float(f1_score(y_validation, y_pred, zero_division=0)),
        "roc_auc": metric_or_zero(roc_auc_score, y_validation, y_score),
    }

    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "model": model,
        "feature_columns": list(X_train.columns),
        "target_column": "churn_label",
        "training_metadata": {
            "algorithm": "sklearn.linear_model.LogisticRegression",
            "hyperparameters": {
                "C": args.C,
                "max_iter": args.max_iter,
                "class_weight": args.class_weight,
                "random_state": args.random_state,
            },
            "validation_metrics": metrics,
        },
    }
    joblib.dump(bundle, model_dir / "model.joblib")
    (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"validation:accuracy={metrics['accuracy']:.6f}")
    print(f"validation:precision={metrics['precision']:.6f}")
    print(f"validation:recall={metrics['recall']:.6f}")
    print(f"validation:f1={metrics['f1']:.6f}")
    print(f"validation:roc_auc={metrics['roc_auc']:.6f}")


if __name__ == "__main__":
    main()
