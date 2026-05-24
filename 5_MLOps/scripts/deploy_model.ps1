$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m src.deploy_model @args
python -m src.smoke_test_endpoint

