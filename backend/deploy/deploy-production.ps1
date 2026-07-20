param(
    [switch]$NoConfirmChangeset
)

$ErrorActionPreference = "Stop"

$backendRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$parameterFile = Join-Path $PSScriptRoot "production.parameters.json"
$configFile = Join-Path $backendRoot "samconfig.production.toml"
$templateFile = Join-Path $backendRoot "template.yaml"

Push-Location $backendRoot
try {
    $python = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
    & $python deploy\validate_production_config.py --parameters $parameterFile
    if ($LASTEXITCODE -ne 0) { throw "Production configuration validation failed." }

    $commit = (git rev-parse HEAD).Trim()
    $version = (git describe --tags --always).Trim()
    $buildTimestamp = [DateTime]::UtcNow.ToString("o")
    # SAM reparses each Key=Value argument with a quote-aware parser.
    $overrides = @()
    $parameters = Get-Content -Raw $parameterFile | ConvertFrom-Json
    foreach ($property in $parameters.PSObject.Properties) {
        # SAM parses each Key=Value argument with its own quote-aware parser.
        # Preserve JSON quotes as literal characters before escaping spaces.
        $escapedValue = ([string]$property.Value).Replace('"', '\"').Replace(" ", "\ ")
        $overrides += "$($property.Name)=$escapedValue"
    }
    $overrides += "GitCommit=$commit"
    $overrides += "AppVersion=$version"
    $overrides += "BuildTimestamp=$buildTimestamp"

    sam validate --lint --template-file $templateFile
    if ($LASTEXITCODE -ne 0) { throw "SAM validation failed." }
    sam build --template-file $templateFile
    if ($LASTEXITCODE -ne 0) { throw "SAM build failed." }
    $deployArguments = @(
        "--config-file", $configFile,
        "--config-env", "production",
        "--parameter-overrides"
    ) + $overrides
    if ($NoConfirmChangeset) {
        $deployArguments += "--no-confirm-changeset"
    }
    sam deploy @deployArguments
    if ($LASTEXITCODE -ne 0) { throw "SAM deployment failed." }
    & $python deploy\post_deploy_verify.py --stack-name lifeledger-api --expected-commit $commit
    if ($LASTEXITCODE -ne 0) { throw "Post-deployment verification failed." }
}
finally {
    Pop-Location
}
