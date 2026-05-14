#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.submit_hpo_job
python -m src.evaluate_model --model-name optimized
