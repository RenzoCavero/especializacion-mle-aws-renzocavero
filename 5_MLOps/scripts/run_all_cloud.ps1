$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m src.deploy_infra
python -m src.lab_runner all
