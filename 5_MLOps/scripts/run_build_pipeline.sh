#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.create_or_update_pipeline
python -m src.run_build_pipeline "$@"

