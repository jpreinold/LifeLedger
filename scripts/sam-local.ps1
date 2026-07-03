$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"

Set-Location $backendDir

$env:AWS_PROFILE = "lifeledger"
$env:AWS_REGION = "us-east-1"

sam build
sam local start-api --env-vars env.local.json
