#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${STACK_NAME:-ml-training-opt-lab}"
PROJECT_NAME="${PROJECT_NAME:-ml-model-training-optimization}"
ENVIRONMENT="${ENVIRONMENT:-lab}"
RESOURCE_PREFIX="${RESOURCE_PREFIX:-ml-training-opt-lab}"
S3_BUCKET_NAME="${S3_BUCKET_NAME:-}"

PROFILE_ARGS=()
if [[ -n "${AWS_PROFILE:-}" ]]; then
  PROFILE_ARGS=(--profile "$AWS_PROFILE")
fi

aws cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --template-file infra/cloudformation/template.yaml \
  --capabilities CAPABILITY_IAM \
  --region "$AWS_REGION" \
  "${PROFILE_ARGS[@]}" \
  --parameter-overrides \
    ProjectName="$PROJECT_NAME" \
    Environment="$ENVIRONMENT" \
    ResourcePrefix="$RESOURCE_PREFIX" \
    S3BucketName="$S3_BUCKET_NAME"

python -m src.fetch_stack_outputs

echo "Infrastructure deployed. Generated outputs were written to .env.cloud"
