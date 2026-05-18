from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fraud_lab.aws.clients import FraudAwsClients
from fraud_lab.aws.config import FraudAwsConfig, load_fraud_aws_config
from fraud_lab.aws.event_bus import SqsPredictionEventBus
from fraud_lab.aws.feature_store import AwsFeatureStore
from fraud_lab.aws.operational_store import DynamoDbDecisionStore
from fraud_lab.aws.s3_data_lake import S3DataLake
from fraud_lab.common.cleaning import clean_transaction
from fraud_lab.common.time_utils import now_request_id
from fraud_lab.config import should_write_last_seen_features
from fraud_lab.features.current_transaction_features import build_current_transaction_features
from fraud_lab.features.feature_contract import FEATURE_VERSION, MODEL_VERSION, default_contract
from fraud_lab.features.feature_vector import assemble_feature_vector
from fraud_lab.model.model_loader import load_model_endpoint
from fraud_lab.schemas import ScoringResult


class AwsFraudScoringService:
    """Fraud Scoring Service usando servicios AWS reales para stores y eventos."""

    def __init__(
        self,
        config: FraudAwsConfig | None = None,
        clients: FraudAwsClients | None = None,
    ) -> None:
        self.config = config or load_fraud_aws_config()
        self.clients = clients or FraudAwsClients(self.config)
        self.s3_lake = S3DataLake(self.config, self.clients)
        self.feature_store = AwsFeatureStore(self.config, self.clients, self.s3_lake)
        self.decision_store = DynamoDbDecisionStore(self.config, self.clients)
        self.event_bus = SqsPredictionEventBus(self.config, self.clients)
        self.local_endpoint = load_model_endpoint()
        self.contract = default_contract()

    def _invoke_endpoint(
        self,
        feature_values: dict[str, float],
        ordered_values: list[float],
        request_id: str,
    ) -> dict[str, Any]:
        endpoint_metadata = self.config.lab_config.metadata_path("fraud_realtime_endpoint.json")
        should_use_endpoint = self.config.fraud_use_sagemaker_endpoint or Path(endpoint_metadata).exists()
        if not should_use_endpoint:
            return self.local_endpoint.predict(feature_values, request_id=request_id)
        payload = {
            "request_id": request_id,
            "features": feature_values,
            "ordered_values": ordered_values,
        }
        response = self.clients.sagemaker_runtime.invoke_endpoint(
            EndpointName=self.config.fraud_endpoint_name,
            ContentType="application/json",
            Accept="application/json",
            Body=json.dumps(payload).encode("utf-8"),
        )
        raw_body = response["Body"].read().decode("utf-8")
        parsed = json.loads(raw_body)
        if isinstance(parsed, list) and parsed:
            parsed = parsed[0]
        if not isinstance(parsed, dict):
            parsed = {"score": float(parsed)}
        score = float(parsed.get("fraud_score", parsed.get("score", 0.0)))
        if "decision" in parsed:
            decision = str(parsed["decision"])
        elif score >= 0.8:
            decision = "reject"
        elif score >= 0.5:
            decision = "manual_review"
        else:
            decision = "approve"
        return {
            "fraud_score": score,
            "decision": decision,
            "reason_codes": list(parsed.get("reason_codes", [])),
            "model_version": str(parsed.get("model_version", MODEL_VERSION)),
            "feature_version": str(parsed.get("feature_version", FEATURE_VERSION)),
        }

    def _persist_trace(
        self,
        raw_event: dict[str, Any],
        cleaned_event: dict[str, Any],
        feature_vector: dict[str, Any],
        prediction_event: dict[str, Any],
    ) -> dict[str, str]:
        base_name = (
            f"{cleaned_event['transaction_id']}_{prediction_event['request_id']}.json"
        )
        return {
            "raw_event": self.s3_lake.put_json(
                ("operational", "inference-logs", "raw-events", base_name),
                raw_event,
            ),
            "cleaned_event": self.s3_lake.put_json(
                ("operational", "inference-logs", "cleaned-events", base_name),
                cleaned_event,
            ),
            "feature_vector": self.s3_lake.put_json(
                ("operational", "inference-logs", "feature-vectors", base_name),
                feature_vector,
            ),
            "prediction_event": self.s3_lake.put_json(
                ("operational", "inference-logs", "predictions", base_name),
                prediction_event,
            ),
        }

    def _emit_async_event(
        self,
        raw_event: dict[str, Any],
        cleaned_event: dict[str, Any],
        prediction_event: dict[str, Any],
        trace_uris: dict[str, str],
    ) -> str:
        event = {
            "event_type": "fraud_prediction_completed",
            "raw_event": raw_event,
            "cleaned_event": cleaned_event,
            "prediction_event": prediction_event,
            "trace_uris": trace_uris,
        }
        return self.event_bus.emit(event)

    def _persist_last_transaction_features_for_future(
        self,
        cleaned_event: dict[str, Any],
    ) -> None:
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
        self.feature_store.put_record("last_transaction_features", record)
        self.feature_store.append_offline_export("last_transaction_features", [record])

    def score_transaction(self, raw_event: dict[str, Any]) -> dict[str, Any]:
        start = time.perf_counter()
        request_id = now_request_id()
        cleaned = clean_transaction(raw_event)
        current_features, warnings = build_current_transaction_features(cleaned)
        historical_features = self.feature_store.get_many_for_transaction(cleaned)
        feature_vector = assemble_feature_vector(
            cleaned,
            current_features=current_features,
            online_features=historical_features,
            contract=self.contract,
            warnings=warnings,
        )
        prediction = self._invoke_endpoint(
            feature_vector.values,
            feature_vector.ordered_values,
            request_id,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        result = ScoringResult(
            transaction_id=cleaned["transaction_id"],
            request_id=request_id,
            fraud_score=float(prediction["fraud_score"]),
            decision=str(prediction["decision"]),
            reason_codes=list(prediction.get("reason_codes", [])),
            model_version=str(prediction.get("model_version", MODEL_VERSION)),
            feature_version=str(prediction.get("feature_version", FEATURE_VERSION)),
            latency_ms=latency_ms,
        ).to_dict()
        endpoint_name = (
            self.config.fraud_endpoint_name
            if self.config.fraud_use_sagemaker_endpoint
            else "ModelEndpointSimulator"
        )
        prediction_event = {
            **result,
            "warnings": feature_vector.warnings,
            "endpoint_name": endpoint_name,
        }
        trace_uris = self._persist_trace(
            raw_event,
            cleaned,
            feature_vector.to_dict(),
            prediction_event,
        )
        self.decision_store.put_decision(prediction_event)
        message_id = self._emit_async_event(raw_event, cleaned, prediction_event, trace_uris)
        if should_write_last_seen_features():
            self._persist_last_transaction_features_for_future(cleaned)
        return {
            **prediction_event,
            "trace_uris": trace_uris,
            "async_message_id": message_id,
        }
