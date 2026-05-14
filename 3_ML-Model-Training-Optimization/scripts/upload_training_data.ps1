$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python -m src.generate_sample_data
python -m src.upload_raw_data
