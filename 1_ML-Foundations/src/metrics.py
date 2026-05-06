"""Small metric helpers used by the local fraud scoring lab."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return float(value)


def roc_auc_score(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    """Compute ROC AUC with the rank-sum formulation."""

    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score).astype(float)
    positives = y_true == 1
    negatives = y_true == 0
    n_pos = int(positives.sum())
    n_neg = int(negatives.sum())
    if n_pos == 0 or n_neg == 0:
        return None

    order = np.argsort(y_score)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(y_score) + 1, dtype=float)

    # Average tied ranks.
    sorted_scores = y_score[order]
    start = 0
    while start < len(sorted_scores):
        end = start + 1
        while end < len(sorted_scores) and sorted_scores[end] == sorted_scores[start]:
            end += 1
        if end - start > 1:
            avg_rank = ranks[order[start:end]].mean()
            ranks[order[start:end]] = avg_rank
        start = end

    rank_sum_pos = ranks[positives].sum()
    auc = (rank_sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return _safe_float(auc)


def average_precision_score(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    """Compute average precision, a PR AUC style metric for imbalanced data."""

    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score).astype(float)
    total_pos = int((y_true == 1).sum())
    if total_pos == 0:
        return None

    order = np.argsort(-y_score)
    sorted_true = y_true[order]
    tp = np.cumsum(sorted_true == 1)
    fp = np.cumsum(sorted_true == 0)
    precision = tp / np.maximum(tp + fp, 1)
    recall = tp / total_pos

    previous_recall = 0.0
    ap = 0.0
    for idx, label in enumerate(sorted_true):
        if label == 1:
            ap += (recall[idx] - previous_recall) * precision[idx]
            previous_recall = recall[idx]
    return _safe_float(ap)


def confusion_counts(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, int]:
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    return {
        "true_positive": int(((y_true == 1) & (y_pred == 1)).sum()),
        "true_negative": int(((y_true == 0) & (y_pred == 0)).sum()),
        "false_positive": int(((y_true == 0) & (y_pred == 1)).sum()),
        "false_negative": int(((y_true == 1) & (y_pred == 0)).sum()),
    }


def binary_classification_metrics(
    y_true: np.ndarray,
    y_score: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score).astype(float)
    y_pred = (y_score >= threshold).astype(int)
    counts = confusion_counts(y_true, y_pred)

    tp = counts["true_positive"]
    tn = counts["true_negative"]
    fp = counts["false_positive"]
    fn = counts["false_negative"]
    total = max(tp + tn + fp + fn, 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    specificity = tn / max(tn + fp, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)

    return {
        "threshold": float(threshold),
        "accuracy": _safe_float((tp + tn) / total),
        "precision": _safe_float(precision),
        "recall": _safe_float(recall),
        "specificity": _safe_float(specificity),
        "f1": _safe_float(f1),
        "roc_auc": roc_auc_score(y_true, y_score),
        "pr_auc": average_precision_score(y_true, y_score),
        "confusion_matrix": counts,
        "positive_rate": _safe_float(float(y_pred.mean())),
        "actual_fraud_rate": _safe_float(float(y_true.mean())),
        "rows": int(total),
    }


def choose_threshold(
    y_true: np.ndarray,
    y_score: np.ndarray,
    min_recall: float = 0.70,
) -> tuple[float, dict[str, Any]]:
    """Pick a threshold that favors F1 while respecting a recall floor when possible."""

    candidates = np.linspace(0.10, 0.90, 81)
    scored = []
    for threshold in candidates:
        metrics = binary_classification_metrics(y_true, y_score, float(threshold))
        scored.append((float(threshold), metrics))

    eligible = [item for item in scored if (item[1]["recall"] or 0.0) >= min_recall]
    pool = eligible or scored
    best = max(pool, key=lambda item: (item[1]["f1"] or 0.0, item[1]["recall"] or 0.0))
    return best

