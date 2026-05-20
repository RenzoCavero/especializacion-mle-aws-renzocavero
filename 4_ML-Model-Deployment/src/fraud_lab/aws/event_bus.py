from __future__ import annotations

import json
from typing import Any

from fraud_lab.aws.clients import FraudAwsClients
from fraud_lab.aws.config import FraudAwsConfig, load_fraud_aws_config


class SqsPredictionEventBus:
    """Cola de eventos asincronos para actualizacion posterior de lake/features."""

    def __init__(
        self,
        config: FraudAwsConfig | None = None,
        clients: FraudAwsClients | None = None,
    ) -> None:
        self.config = config or load_fraud_aws_config()
        self.clients = clients or FraudAwsClients(self.config)
        self.sqs = self.clients.sqs

    def emit(self, event: dict[str, Any]) -> str:
        response = self.sqs.send_message(
            QueueUrl=self.config.fraud_event_queue_url,
            MessageBody=json.dumps(event, sort_keys=True),
        )
        return str(response["MessageId"])

    def receive(self, max_messages: int = 10) -> list[dict[str, Any]]:
        response = self.sqs.receive_message(
            QueueUrl=self.config.fraud_event_queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=1,
        )
        messages = []
        for message in response.get("Messages", []):
            messages.append(
                {
                    "receipt_handle": message["ReceiptHandle"],
                    "body": json.loads(message["Body"]),
                }
            )
        return messages

    def delete(self, receipt_handle: str) -> None:
        self.sqs.delete_message(
            QueueUrl=self.config.fraud_event_queue_url,
            ReceiptHandle=receipt_handle,
        )

