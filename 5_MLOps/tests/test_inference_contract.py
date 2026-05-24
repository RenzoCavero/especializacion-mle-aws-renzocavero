from __future__ import annotations

import json

from training.inference import output_fn


def test_output_fn_returns_json_content_type():
    body, content_type = output_fn([{"prediction": 1, "probability": 0.91}], "application/json")
    assert content_type == "application/json"
    assert json.loads(body)["prediction"] == 1
