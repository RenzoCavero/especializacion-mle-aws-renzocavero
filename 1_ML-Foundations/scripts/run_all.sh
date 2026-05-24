#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python -m src.generate_dataset
python -m src.data_preparation
python -m src.train
python -m src.evaluate
python -m src.batch_inference
python -m src.monitor
python -m src.model_card

echo "Full local ML flow completed."

