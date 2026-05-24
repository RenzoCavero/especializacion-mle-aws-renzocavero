from __future__ import annotations

import time
from typing import Any

from fraud_lab.common.cleaning import clean_transaction
from fraud_lab.common.io_utils import write_json
from fraud_lab.common.time_utils import now_request_id
from fraud_lab.config import data_dir, ensure_fraud_dirs, should_write_last_seen_features
from fraud_lab.feature_store.online_store import LocalOnlineFeatureStore
from fraud_lab.features.current_transaction_features import build_current_transaction_features
from fraud_lab.features.feature_contract import default_contract
from fraud_lab.features.feature_vector import assemble_feature_vector
from fraud_lab.model.model_loader import load_model_endpoint
from fraud_lab.monitoring.inference_logger import persist_decision, persist_inference_trace
from fraud_lab.schemas import ScoringResult


class FraudScoringService:
    """Simula API Gateway/ALB -> Fraud Scoring Service -> SageMaker Endpoint."""

    def __init__(self) -> None:
        ensure_fraud_dirs()
        self.online_store = LocalOnlineFeatureStore()
        self.endpoint = load_model_endpoint()
        self.contract = default_contract()

    def _emit_async_event(
        self,
        raw_event: dict[str, Any],
        cleaned_event: dict[str, Any],
        prediction_event: dict[str, Any],
    ) -> None:
        event = {
            "event_type": "fraud_prediction_completed",
            "raw_event": raw_event,
            "cleaned_event": cleaned_event,
            "prediction_event": prediction_event,
        }
        file_name = f"{cleaned_event['transaction_id']}_{prediction_event['request_id']}.json"
        write_json(data_dir() / "events" / "pending" / file_name, event)

    def _persist_last_transaction_features_for_future(self, cleaned_event: dict[str, Any]) -> None:
        record = {
            "user_id": cleaned_event["user_id"],
            "event_time": cleaned_event["timestamp"],
            "last_transaction_amount": cleaned_event["amount_pen"],
            "last_transaction_country": cleaned_event["country"],
            "last_transaction_timestamp": cleaned_event["timestamp"],
            "last_channel_used": cleaned_event["channel"],
            "last_merchant_id": cleaned_event["merchant_id"],
            "last_device_id": cleaned_event["device_id"],
        }
        self.online_store.put_record("last_transaction_features", record)

    def score_transaction(self, raw_event: dict[str, Any]) -> dict[str, Any]:
        start = time.perf_counter()
        request_id = now_request_id()
        cleaned = clean_transaction(raw_event)
        current_features, warnings = build_current_transaction_features(cleaned)
        historical_features = self.online_store.get_many_for_transaction(cleaned)
        feature_vector = assemble_feature_vector(
            cleaned,
            current_features=current_features,
            online_features=historical_features,
            contract=self.contract,
            warnings=warnings,
        )
        prediction = self.endpoint.predict(feature_vector.values, request_id=request_id)
        latency_ms = int((time.perf_counter() - start) * 1000)
        result = ScoringResult(
            transaction_id=cleaned["transaction_id"],
            request_id=request_id,
            fraud_score=float(prediction["fraud_score"]),
            decision=str(prediction["decision"]),
            reason_codes=list(prediction["reason_codes"]),
            model_version=str(prediction["model_version"]),
            feature_version=str(prediction["feature_version"]),
            latency_ms=latency_ms,
        ).to_dict()
        prediction_event = {
            **result,
            "warnings": feature_vector.warnings,
            "endpoint_name": "ModelEndpointSimulator",
        }
        persist_inference_trace(raw_event, cleaned, feature_vector.to_dict(), prediction_event)
        persist_decision(prediction_event)
        self._emit_async_event(raw_event, cleaned, prediction_event)
        if should_write_last_seen_features():
            self._persist_last_transaction_features_for_future(cleaned)
        return prediction_event

