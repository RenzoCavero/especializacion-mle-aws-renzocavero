param(
    [string]$Steps = $(if ($env:PIPELINE_STEPS) { $env:PIPELINE_STEPS } else { "all" })
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m src.run_processing_job --steps $Steps

