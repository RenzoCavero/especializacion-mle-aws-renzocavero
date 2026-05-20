from __future__ import annotations

from fraud_lab.features.feature_contract import write_default_artifacts
from fraud_lab.model.endpoint_simulator import ModelEndpointSimulator


def load_model_endpoint() -> ModelEndpointSimulator:
    write_default_artifacts()
    return ModelEndpointSimulator()

