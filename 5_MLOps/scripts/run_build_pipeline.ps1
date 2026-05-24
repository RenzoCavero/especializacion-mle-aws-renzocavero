$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m src.create_or_update_pipeline
python -m src.run_build_pipeline @args

