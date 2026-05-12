$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m src.deploy_infra
python -m src.generate_sample_data
python -m src.upload_raw_data
python -m src.register_catalog
python -m src.run_processing_job --steps all
python -m src.download_reports
python -m src.validate_outputs

