#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

python -m src.deploy_infra
python -m fraud_lab.aws.pipelines.generate_synthetic_data_aws
python -m fraud_lab.aws.pipelines.raw_to_cleaned_aws
python -m fraud_lab.aws.pipelines.cleaned_to_curated_aws
python -m fraud_lab.aws.pipelines.curated_to_offline_features_aws
python -m fraud_lab.aws.model_registry
python -m fraud_lab.aws.deploy_endpoint
python -m fraud_lab.aws.pipelines.online_predict_aws
python -m fraud_lab.aws.pipelines.async_update_online_features_aws
python -m fraud_lab.aws.pipelines.batch_prediction_aws
python -m fraud_lab.aws.pipelines.build_retraining_dataset_aws

echo "Flujo fraude cloud completado. Ejecuta python -m src.lab_runner cleanup para borrar endpoint/model/Feature Groups."
echo "Para teardown total opcional: python -m fraud_lab.aws.pipelines.full_cleanup_aws --all"
