$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m src.create_feedback_loop
python -m src.create_eventbridge_rule

