#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.deploy_infra
python -m src.lab_runner all
