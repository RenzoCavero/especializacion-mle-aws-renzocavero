$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m src.configure_data_capture
python -m src.generate_baseline
python -m src.create_monitoring_schedule
python -m src.create_cloudwatch_alarm

