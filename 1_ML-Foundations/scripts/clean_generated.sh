#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python scripts/clean_generated.py "$@"

