"""FastAPI app for local real-time fraud scoring."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd
from fastapi import FastAPI, HTTPException

from src.api.schemas import HealthResponse, PredictionResponse, TransactionRequest
from src.config import DECISION_BLOCK_THRESHOLD, DECISION_REVIEW_THRESHOLD, MODEL_PATH, project_relative
from src.data_preparation import build_features
from src.modeling import decision_from_probability, load_model_bundle, predict_proba


app = FastAPI(
    title="AWS ML Foundations Local Fraud Scoring API",
    version="1.0.0",
    description="Local FastAPI equivalent of a SageMaker real-time endpoint.",
)


@lru_cache(maxsize=1)
def get_model_bundle():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model artifact not found at {MODEL_PATH}. Run `make train` first.")
    return load_model_bundle(MODEL_PATH)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", model_loaded=MODEL_PATH.exists(), model_path=project_relative(MODEL_PATH))


@app.post("/predict", response_model=PredictionResponse)
def predict(payload: TransactionRequest) -> PredictionResponse:
    try:
        bundle = get_model_bundle()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    row = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    if row.get("transaction_id") is None:
        row["transaction_id"] = "api_request"
    if row.get("event_timestamp") is None:
        row["event_timestamp"] = "2026-01-01 00:00:00"

    try:
        feature_df = build_features(pd.DataFrame([row]))
        probability = float(predict_proba(bundle, feature_df)[0])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid payload or feature transformation error: {exc}") from exc

    decision = decision_from_probability(
        probability,
        review_threshold=float(bundle.get("threshold", DECISION_REVIEW_THRESHOLD)),
        block_threshold=DECISION_BLOCK_THRESHOLD,
    )
    return PredictionResponse(
        transaction_id=row.get("transaction_id"),
        fraud_probability=round(probability, 6),
        risk_decision=decision,
        model_version=bundle["model_version"],
        threshold=float(bundle["threshold"]),
    )
