param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not $Args -or $Args.Count -eq 0) {
    python -m src.lab_runner list
    exit 0
}

switch ($Args[0]) {
    "all" {
        python -m src.lab_runner all
    }
    "list" {
        python -m src.lab_runner list
    }
    "cleanup" {
        python -m src.lab_runner cleanup
    }
    "step" {
        if ($Args.Count -lt 2) {
            throw "Usage: .\scripts\lab.ps1 step <identifier>"
        }
        python -m src.lab_runner step $Args[1]
    }
    default {
        python -m src.lab_runner step $Args[0]
    }
}
