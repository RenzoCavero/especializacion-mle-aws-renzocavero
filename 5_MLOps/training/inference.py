"""SageMaker inference entry point for the trained churn model."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


def model_fn(model_dir: str) -> Any:
    return joblib.load(Path(model_dir) / "model.joblib")


def input_fn(request_body: str | bytes, content_type: str = "application/json") -> pd.DataFrame:
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")

    if content_type in {"application/json", "application/jsonlines"}:
        payload = json.loads(request_body)
        if isinstance(payload, dict):
            payload = [payload]
        return pd.DataFrame(payload)
    if content_type in {"text/csv", "application/csv"}:
        return pd.read_csv(io.StringIO(request_body))
    raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(input_data: pd.DataFrame, model: Any) -> list[dict[str, float | int]]:
    predictions = model.predict(input_data)
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(input_data)[:, 1]
    else:
        probabilities = predictions
    return [
        {"prediction": int(pred), "probability": float(prob)}
        for pred, prob in zip(predictions, probabilities)
    ]


def output_fn(prediction: Any, accept: str = "application/json") -> tuple[str, str]:
    if accept == "application/json":
        payload = prediction[0] if isinstance(prediction, list) and len(prediction) == 1 else prediction
        return json.dumps(payload), "application/json"
    if accept == "text/csv":
        return "\n".join(f"{row['prediction']},{row['probability']}" for row in prediction), "text/csv"
    raise ValueError(f"Unsupported accept type: {accept}")
