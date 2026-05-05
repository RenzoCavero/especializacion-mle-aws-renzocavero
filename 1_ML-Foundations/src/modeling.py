"""Minimal preprocessing, training and scoring utilities."""

from __future__ import annotations

import json
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config import (
    CATEGORICAL_FEATURES,
    DECISION_BLOCK_THRESHOLD,
    DECISION_REVIEW_THRESHOLD,
    FEATURE_COLUMNS,
    MODEL_VERSION,
    NUMERIC_FEATURES,
    RANDOM_SEED,
    TARGET_COLUMN,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fit_preprocessor(df: pd.DataFrame) -> dict[str, Any]:
    numeric_stats = {}
    for column in NUMERIC_FEATURES:
        values = pd.to_numeric(df[column], errors="coerce")
        mean = float(values.mean())
        std = float(values.std(ddof=0))
        if not np.isfinite(std) or std < 1e-8:
            std = 1.0
        numeric_stats[column] = {
            "mean": 0.0 if not np.isfinite(mean) else mean,
            "std": std,
            "median": float(values.median()) if np.isfinite(values.median()) else 0.0,
        }

    categorical_values = {}
    for column in CATEGORICAL_FEATURES:
        categories = sorted(str(value) for value in df[column].fillna("unknown").unique())
        categorical_values[column] = categories or ["unknown"]

    feature_names = list(NUMERIC_FEATURES)
    for column in CATEGORICAL_FEATURES:
        feature_names.extend([f"{column}={category}" for category in categorical_values[column]])

    return {
        "numeric_stats": numeric_stats,
        "categorical_values": categorical_values,
        "feature_names": feature_names,
    }


def transform_features(df: pd.DataFrame, preprocessor: dict[str, Any]) -> np.ndarray:
    missing = [column for column in FEATURE_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")

    matrices = []
    for column in NUMERIC_FEATURES:
        stats = preprocessor["numeric_stats"][column]
        values = pd.to_numeric(df[column], errors="coerce").fillna(stats["median"])
        scaled = (values.to_numpy(dtype=float) - stats["mean"]) / stats["std"]
        matrices.append(scaled.reshape(-1, 1))

    for column in CATEGORICAL_FEATURES:
        categories = preprocessor["categorical_values"][column]
        values = df[column].fillna("unknown").astype(str)
        encoded = np.zeros((len(df), len(categories)), dtype=float)
        category_to_index = {category: idx for idx, category in enumerate(categories)}
        for row_idx, value in enumerate(values):
            col_idx = category_to_index.get(value)
            if col_idx is not None:
                encoded[row_idx, col_idx] = 1.0
        matrices.append(encoded)

    return np.hstack(matrices).astype(float)


def _sigmoid(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, -35, 35)
    return 1.0 / (1.0 + np.exp(-values))


def train_logistic_regression(
    x_train: np.ndarray,
    y_train: np.ndarray,
    learning_rate: float = 0.06,
    epochs: int = 900,
    l2: float = 0.01,
    seed: int = RANDOM_SEED,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    n_rows, n_features = x_train.shape
    weights = rng.normal(0.0, 0.01, size=n_features)
    bias = 0.0

    y_train = y_train.astype(float)
    positives = max(float(y_train.sum()), 1.0)
    negatives = max(float(len(y_train) - y_train.sum()), 1.0)
    pos_weight = len(y_train) / (2.0 * positives)
    neg_weight = len(y_train) / (2.0 * negatives)
    sample_weights = np.where(y_train == 1.0, pos_weight, neg_weight)

    losses: list[float] = []
    for epoch in range(epochs):
        scores = x_train @ weights + bias
        probabilities = _sigmoid(scores)
        errors = (probabilities - y_train) * sample_weights
        gradient_w = (x_train.T @ errors) / n_rows + l2 * weights
        gradient_b = float(errors.mean())
        weights -= learning_rate * gradient_w
        bias -= learning_rate * gradient_b

        if epoch % 100 == 0 or epoch == epochs - 1:
            eps = 1e-12
            weighted_loss = -np.mean(
                sample_weights
                * (
                    y_train * np.log(probabilities + eps)
                    + (1.0 - y_train) * np.log(1.0 - probabilities + eps)
                )
            )
            regularization = 0.5 * l2 * float(np.sum(weights**2))
            losses.append(float(weighted_loss + regularization))

    return {
        "weights": weights,
        "bias": float(bias),
        "loss_history": losses,
        "training_rows": int(n_rows),
        "positive_class_weight": float(pos_weight),
        "negative_class_weight": float(neg_weight),
        "learning_rate": float(learning_rate),
        "epochs": int(epochs),
        "l2": float(l2),
    }


def predict_proba_matrix(x_values: np.ndarray, weights: np.ndarray, bias: float) -> np.ndarray:
    return _sigmoid(x_values @ weights + bias)


def predict_proba(bundle: dict[str, Any], df: pd.DataFrame) -> np.ndarray:
    x_values = transform_features(df, bundle["preprocessor"])
    return predict_proba_matrix(x_values, bundle["weights"], float(bundle["bias"]))


def build_model_bundle(
    train_df: pd.DataFrame,
    threshold: float,
    training_metrics: dict[str, Any],
    model_params: dict[str, Any],
) -> dict[str, Any]:
    preprocessor = fit_preprocessor(train_df)
    x_train = transform_features(train_df, preprocessor)
    y_train = train_df[TARGET_COLUMN].to_numpy(dtype=int)
    model = train_logistic_regression(x_train, y_train, **model_params)

    bundle = {
        "model_version": MODEL_VERSION,
        "created_at": utc_now_iso(),
        "preprocessor": preprocessor,
        "weights": model["weights"],
        "bias": model["bias"],
        "threshold": float(threshold),
        "training_metrics": training_metrics,
        "training_details": {
            key: value for key, value in model.items() if key not in {"weights"}
        },
    }
    return bundle


def save_model_bundle(path: Path, bundle: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as file:
        pickle.dump(bundle, file)


def load_model_bundle(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        return pickle.load(file)


def decision_from_probability(
    probability: float,
    review_threshold: float = DECISION_REVIEW_THRESHOLD,
    block_threshold: float = DECISION_BLOCK_THRESHOLD,
) -> str:
    if probability >= block_threshold:
        return "block"
    if probability >= review_threshold:
        return "review"
    return "approve"

