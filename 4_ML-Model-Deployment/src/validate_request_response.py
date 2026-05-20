from __future__ import annotations

import argparse
import json
from typing import Any

from .config import FeatureContract, load_config, load_feature_contract


class ContractError(ValueError):
    """Raised when an inference request or response violates the lab contract."""


def extract_features(payload: dict[str, Any]) -> dict[str, Any]:
    if "features" in payload and isinstance(payload["features"], dict):
        return dict(payload["features"])
    return {
        key: value
        for key, value in payload.items()
        if key not in {"request_id", "customer_id", "transaction_id", "model_version"}
    }


def validate_inference_request(
    payload: dict[str, Any], contract: FeatureContract | None = None
) -> dict[str, float]:
    contract = contract or FeatureContract.standalone()
    features = extract_features(payload)
    if contract.target_column in payload or contract.target_column in features:
        raise ContractError("La columna target no debe enviarse a inferencia.")
    missing = [name for name in contract.inference_features if name not in features]
    if missing:
        raise ContractError("Faltan features requeridas: " + ", ".join(missing))
    clean: dict[str, float] = {}
    for name in contract.inference_features:
        value = features[name]
        if value is None or value == "":
            raise ContractError(f"La feature {name} no puede ser nula.")
        try:
            clean[name] = float(value)
        except (TypeError, ValueError) as exc:
            raise ContractError(f"La feature {name} debe ser numerica.") from exc
    return clean


def decision_from_score(score: float) -> str:
    if score >= 0.75:
        return "review"
    if score >= 0.5:
        return "monitor"
    return "approve"


def normalize_response(raw: Any, model_version: str = "unknown", request_id: str = "") -> dict[str, Any]:
    if isinstance(raw, dict):
        response = dict(raw)
    elif isinstance(raw, list) and raw:
        response = normalize_response(raw[0], model_version=model_version, request_id=request_id)
    else:
        try:
            response = {"score": float(raw)}
        except (TypeError, ValueError) as exc:
            raise ContractError("La respuesta del modelo no contiene un score valido.") from exc
    score = float(response.get("score", 0.0))
    response["score"] = score
    response["predicted_label"] = int(response.get("predicted_label", 1 if score >= 0.5 else 0))
    response["decision"] = response.get("decision") or decision_from_score(score)
    response["model_version"] = response.get("model_version") or model_version
    response["request_id"] = response.get("request_id") or request_id
    return validate_model_response(response)


def validate_model_response(response: dict[str, Any]) -> dict[str, Any]:
    required = {"score", "predicted_label", "decision", "model_version", "request_id"}
    missing = required.difference(response)
    if missing:
        raise ContractError("Faltan campos en la respuesta: " + ", ".join(sorted(missing)))
    score = float(response["score"])
    if not 0.0 <= score <= 1.0:
        raise ContractError("score debe estar entre 0 y 1.")
    response["score"] = score
    response["predicted_label"] = int(response["predicted_label"])
    if response["decision"] not in {"approve", "monitor", "review", "decline"}:
        raise ContractError("decision no pertenece al conjunto esperado.")
    return response


def example_request(contract: FeatureContract | None = None) -> dict[str, Any]:
    contract = contract or FeatureContract.standalone()
    values = {
        "age": 42,
        "income": 62000,
        "account_tenure_months": 18,
        "monthly_spend": 180,
        "support_tickets_90d": 2,
    }
    return {
        contract.realtime_lookup_key: "CUST-0001",
        "features": {name: values.get(name, 1.0) for name in contract.inference_features},
    }


def example_response() -> dict[str, Any]:
    return {
        "score": 0.82,
        "predicted_label": 1,
        "decision": "review",
        "model_version": "standalone-v1",
        "request_id": "example-request",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida contratos de request/response.")
    parser.add_argument("--examples", action="store_true", help="Imprimir ejemplos JSON.")
    args = parser.parse_args()
    config = load_config(require_aws=False)
    contract = load_feature_contract(config)
    request = example_request(contract)
    response = example_response()
    validate_inference_request(request, contract)
    validate_model_response(response)
    if args.examples:
        print(json.dumps({"request": request, "response": response}, indent=2))
    else:
        print("Contratos de request/response validos.")


if __name__ == "__main__":
    main()
