#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
STEPS="${1:-${PIPELINE_STEPS:-all}}"
python -m src.run_processing_job --steps "${STEPS}"

