#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

make deploy-infra
make data
make upload-raw
make prepare-feature-sources
make create-feature-group
make ingest-features
make validate-online-store
make query-offline-store
make processing
make train-baseline
make evaluate-baseline
make hpo
make compare-models
make register-model
make export-feature-metadata
make training-report
make model-card
make create-pipeline
make download-reports
make validate
