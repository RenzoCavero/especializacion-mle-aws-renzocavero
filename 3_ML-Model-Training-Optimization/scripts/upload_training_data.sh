#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.generate_sample_data
python -m src.upload_raw_data
python -m src.prepare_feature_sources
