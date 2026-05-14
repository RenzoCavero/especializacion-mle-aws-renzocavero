$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

$region = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }
$stackName = if ($env:STACK_NAME) { $env:STACK_NAME } else { "ml-training-opt-lab" }
$projectName = if ($env:PROJECT_NAME) { $env:PROJECT_NAME } else { "ml-model-training-optimization" }
$environment = if ($env:ENVIRONMENT) { $env:ENVIRONMENT } else { "lab" }
$resourcePrefix = if ($env:RESOURCE_PREFIX) { $env:RESOURCE_PREFIX } else { "ml-training-opt-lab" }
$bucketName = if ($env:S3_BUCKET_NAME) { $env:S3_BUCKET_NAME } else { "" }

$profileArgs = @()
if ($env:AWS_PROFILE) { $profileArgs = @("--profile", $env:AWS_PROFILE) }

aws cloudformation deploy `
  --stack-name $stackName `
  --template-file infra/cloudformation/template.yaml `
  --capabilities CAPABILITY_IAM `
  --region $region `
  @profileArgs `
  --parameter-overrides `
    ProjectName=$projectName `
    Environment=$environment `
    ResourcePrefix=$resourcePrefix `
    S3BucketName=$bucketName

python -m src.fetch_stack_outputs
Write-Host "Infrastructure deployed. Generated outputs were written to .env.cloud"
