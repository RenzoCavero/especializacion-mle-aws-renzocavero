$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

python -m src.generate_sample_data
.\scripts\deploy_infra.ps1
python -m src.upload_raw_data
python -m src.prepare_feature_sources
python -m src.create_feature_group
python -m src.submit_feature_ingestion_job
python -m src.get_online_features
python -m src.query_offline_store
python -m src.submit_processing_job
python -m src.submit_training_job
python -m src.evaluate_model --model-name baseline
python -m src.submit_hpo_job
python -m src.evaluate_model --model-name optimized
python -m src.compare_models
python -m src.register_model
python -m src.export_feature_metadata
python -m src.training_report
python -m src.model_card
python -m src.create_pipeline
python -m src.download_outputs
python -m src.validate_lab
