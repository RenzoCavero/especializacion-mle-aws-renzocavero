param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if ($DryRun) {
    python -m src.clean_local_outputs --dry-run
} else {
    python -m src.clean_local_outputs
}
