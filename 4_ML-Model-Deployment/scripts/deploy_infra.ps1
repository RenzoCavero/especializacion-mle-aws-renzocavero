$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

python -m src.deploy_infra

Write-Host "Infrastructure deployed. Generated outputs were written to .env.cloud"
