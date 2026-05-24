$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")
python scripts/clean_generated.py @args

