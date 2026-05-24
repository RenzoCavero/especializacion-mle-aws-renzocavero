from __future__ import annotations

from pathlib import Path
import json
import tarfile

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score


TARGET_COLUMN = "churn_label"
ID_COLUMNS = ["customer_id", "event_time"]
CATEGORICAL_FEATURES = ["plan_type", "country", "device_type"]
NUMERIC_TRAINING_FEATURES = [
    "age_days",
    "sessions_last_7d",
    "sessions_last_30d",
    "avg_session_duration_last_30d",
    "support_tickets_last_30d",
    "payment_failures_last_90d",
    "days_since_last_login",
    "engagement_score",
]


def ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def prepare_model_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    missing = [col for col in NUMERIC_TRAINING_FEATURES + CATEGORICAL_FEATURES + [TARGET_COLUMN] if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns for processing: {missing}")

    model_df = df[NUMERIC_TRAINING_FEATURES + CATEGORICAL_FEATURES + [TARGET_COLUMN]].copy()
    model_df = pd.get_dummies(model_df, columns=CATEGORICAL_FEATURES, drop_first=False, dtype=int)
    target = model_df.pop(TARGET_COLUMN)
    model_df[TARGET_COLUMN] = target.astype(int)
    metadata = {
        "target_column": TARGET_COLUMN,
        "id_columns": ID_COLUMNS,
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_training_features": NUMERIC_TRAINING_FEATURES,
        "encoded_feature_columns": [column for column in model_df.columns if column != TARGET_COLUMN],
        "transformations": [
            "Drop record identifier and event time for model input.",
            "One-hot encode plan_type, country and device_type.",
            "Keep churn_label only as target for training/evaluation.",
        ],
    }
    return model_df, metadata


def write_json(data: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def extract_model(model_tar_path: str | Path, extract_dir: str | Path) -> Path:
    extract_dir = ensure_dir(extract_dir)
    with tarfile.open(model_tar_path, "r:gz") as tar:
        tar.extractall(path=extract_dir)
    return extract_dir


def load_model_bundle(model_dir: str | Path):
    model_path = Path(model_dir) / "model.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"Could not find {model_path}")
    return joblib.load(model_path)


def evaluate_predictions(y_true, y_pred, y_score=None) -> dict:
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }
    try:
        metrics["roc_auc"] = float(roc_auc_score(y_true, y_score if y_score is not None else y_pred))
    except ValueError:
        metrics["roc_auc"] = 0.0
    return metrics
