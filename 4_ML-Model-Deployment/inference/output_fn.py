from __future__ import annotations

import json
from typing import Any


def output_fn(prediction: list[dict[str, Any]], accept: str = "application/json") -> str:
    accept = (accept or "application/json").split(";")[0].strip().lower()
    enriched = []
    for item in prediction:
        response = dict(item)
        response.setdefault("model_version", "standalone-v1")
        response.setdefault("request_id", "")
        enriched.append(response)

    if accept == "application/json":
        if len(enriched) == 1:
            return json.dumps(enriched[0])
        return json.dumps(enriched)

    if accept in {"text/csv", "application/csv"}:
        return "\n".join(str(item["score"]) for item in enriched)

    return json.dumps(enriched[0] if len(enriched) == 1 else enriched)
