$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

python -m src.generate_dataset
python -m src.data_preparation
python -m src.train
python -m src.evaluate
python -m src.batch_inference
python -m src.monitor
python -m src.model_card

Write-Host "Full local ML flow completed."

