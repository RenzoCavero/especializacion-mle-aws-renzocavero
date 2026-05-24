from __future__ import annotations

import argparse
import json
from pathlib import Path

from fraud_lab.aws.scoring_service import AwsFraudScoringService
from fraud_lab.config import default_online_transaction


def online_predict_aws(input_file: str = "") -> dict[str, object]:
    if input_file:
        raw_event = json.loads(Path(input_file).read_text(encoding="utf-8"))
    else:
        raw_event = default_online_transaction()
    result = AwsFraudScoringService().score_transaction(raw_event)
    print("Prediccion online cloud:")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score one fraud transaction using AWS stores and event resources."
    )
    parser.add_argument(
        "--input-file",
        default="",
        help="JSON local opcional con la transaccion a puntuar.",
    )
    args = parser.parse_args()
    online_predict_aws(args.input_file)


if __name__ == "__main__":
    main()

