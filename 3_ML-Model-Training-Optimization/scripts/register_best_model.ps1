$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python -m src.compare_models
python -m src.register_model
python -m src.export_feature_metadata
