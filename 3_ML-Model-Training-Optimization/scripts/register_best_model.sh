#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.compare_models
python -m src.register_model
python -m src.export_feature_metadata
