from __future__ import annotations

from decimal import Decimal
from typing import Any

from fraud_lab.aws.clients import FraudAwsClients
from fraud_lab.aws.config import FraudAwsConfig, load_fraud_aws_config


def _to_dynamodb_value(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(round(value, 8)))
    if isinstance(value, dict):
        return {str(key): _to_dynamodb_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_dynamodb_value(item) for item in value]
    return value


class DynamoDbDecisionStore:
    """Persistencia operacional de decisiones en DynamoDB."""

    def __init__(
        self,
        config: FraudAwsConfig | None = None,
        clients: FraudAwsClients | None = None,
    ) -> None:
        self.config = config or load_fraud_aws_config()
        self.clients = clients or FraudAwsClients(self.config)
        self.table = self.clients.dynamodb_resource.Table(
            self.config.fraud_decision_table_name
        )

    def put_decision(self, prediction_event: dict[str, Any]) -> None:
        item = {
            "transaction_id": str(prediction_event["transaction_id"]),
            "request_id": str(prediction_event["request_id"]),
            "decision": str(prediction_event["decision"]),
            "fraud_score": float(prediction_event["fraud_score"]),
            "model_version": str(prediction_event["model_version"]),
            "feature_version": str(prediction_event["feature_version"]),
            "latency_ms": int(prediction_event["latency_ms"]),
            "payload": prediction_event,
        }
        self.table.put_item(Item=_to_dynamodb_value(item))

