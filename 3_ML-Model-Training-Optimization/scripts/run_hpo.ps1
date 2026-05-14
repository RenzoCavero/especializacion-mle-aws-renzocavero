$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python -m src.submit_hpo_job
python -m src.evaluate_model --model-name optimized
