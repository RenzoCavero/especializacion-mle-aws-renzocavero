#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.deploy_model "$@"
python -m src.smoke_test_endpoint

