from __future__ import annotations

from io import StringIO
import json
from pathlib import Path

import joblib
import pandas as pd


def model_fn(model_dir: str):
    return joblib.load(Path(model_dir) / "model.joblib")


def input_fn(request_body: str, request_content_type: str):
    if request_content_type == "text/csv":
        return pd.read_csv(StringIO(request_body))
    if request_content_type == "application/json":
        payload = json.loads(request_body)
        if isinstance(payload, dict):
            payload = [payload]
        return pd.DataFrame(payload)
    raise ValueError(f"Unsupported content type: {request_content_type}")


def predict_fn(input_data: pd.DataFrame, model_bundle):
    feature_columns = model_bundle["feature_columns"]
    missing = [column for column in feature_columns if column not in input_data.columns]
    if missing:
        raise ValueError(f"Missing model feature columns: {missing}")
    model = model_bundle["model"]
    scores = model.predict_proba(input_data[feature_columns])[:, 1]
    predictions = model.predict(input_data[feature_columns])
    return pd.DataFrame({"churn_prediction": predictions, "churn_probability": scores})


def output_fn(prediction, accept: str):
    if accept == "application/json":
        return prediction.to_json(orient="records"), accept
    if accept == "text/csv":
        return prediction.to_csv(index=False), accept
    return prediction.to_json(orient="records"), "application/json"
