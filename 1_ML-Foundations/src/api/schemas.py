"""Request and response schemas for the local fraud scoring API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TransactionRequest(BaseModel):
    transaction_id: str | None = Field(default=None, examples=["txn_api_0001"])
    customer_id: str = Field(default="cus_12345", examples=["cus_12345"])
    event_timestamp: str | None = Field(default=None, examples=["2026-01-15 10:30:00"])
    amount: float = Field(default=125.5, ge=0.0)
    merchant_category: str = Field(default="digital_goods")
    country: str = Field(default="PE", min_length=2, max_length=3)
    channel: str = Field(default="mobile")
    device_type: str = Field(default="android")
    hour: int = Field(default=10, ge=0, le=23)
    day_of_week: int = Field(default=2, ge=0, le=6)
    customer_age_days: int = Field(default=365, ge=0)
    transactions_last_24h: int = Field(default=2, ge=0)
    avg_amount_30d: float = Field(default=80.0, gt=0.0)
    chargeback_rate_90d: float = Field(default=0.03, ge=0.0, le=1.0)
    distance_from_home_km: float = Field(default=15.0, ge=0.0)
    is_foreign_transaction: int = Field(default=0, ge=0, le=1)
    is_high_risk_merchant: int = Field(default=1, ge=0, le=1)


class PredictionResponse(BaseModel):
    transaction_id: str | None
    fraud_probability: float
    risk_decision: Literal["approve", "review", "block"]
    model_version: str
    threshold: float


class HealthResponse(BaseModel):
    status: Literal["ok"]
    model_loaded: bool
    model_path: str

