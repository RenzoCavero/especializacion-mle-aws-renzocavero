from __future__ import annotations

import argparse
import json

from fraud_lab.common.io_utils import read_json
from fraud_lab.config import default_online_transaction, path
from fraud_lab.feature_store.seed_feature_store import seed_feature_store
from fraud_lab.scoring.fraud_scoring_service import FraudScoringService


def online_predict(input_path: str = "") -> dict:
    seed_feature_store()
    if input_path:
        payload = read_json(path(input_path))
    else:
        payload = default_online_transaction()
    result = FraudScoringService().score_transaction(payload)
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local real-time fraud scoring simulation.")
    parser.add_argument("--input", default="", help="Ruta JSON relativa al lab con una transaccion.")
    args = parser.parse_args()
    online_predict(args.input)


if __name__ == "__main__":
    main()

