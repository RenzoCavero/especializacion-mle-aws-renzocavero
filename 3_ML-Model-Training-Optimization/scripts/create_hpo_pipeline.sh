#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.create_hpo_pipeline
