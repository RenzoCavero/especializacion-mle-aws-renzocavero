#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.submit_training_job
