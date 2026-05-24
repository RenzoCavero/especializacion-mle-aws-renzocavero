$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m src.generate_sample_data
python -m src.upload_raw_data

