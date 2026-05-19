#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.submit_feature_ingestion_job
