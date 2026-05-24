#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

python -m src.deploy_infra

echo "Infrastructure deployed. Generated outputs were written to .env.cloud"
