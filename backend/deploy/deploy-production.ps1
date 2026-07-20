param(
    [switch]$NoConfirmChangeset
)

$ErrorActionPreference = "Stop"

$backendRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$parameterFile = Join-Path $PSScriptRoot "production.parameters.json"
$configFile = Join-Path $backendRoot "samconfig.production.toml"
$templateFile = Join-Path $backendRoot "template.yaml"
$generatedParameterFile = Join-Path $backendRoot ".aws-sam\production.parameters.yaml"

Push-Location $backendRoot
try {
    $python = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
    & $python deploy\validate_production_config.py --parameters $parameterFile
    if ($LASTEXITCODE -ne 0) { throw "Production configuration validation failed." }

    $commit = (git rev-parse HEAD).Trim()
    $version = (git describe --tags --always).Trim()
    $buildTimestamp = [DateTime]::UtcNow.ToString("o")

    sam validate --lint --template-file $templateFile
    if ($LASTEXITCODE -ne 0) { throw "SAM validation failed." }
    sam build --template-file $templateFile
    if ($LASTEXITCODE -ne 0) { throw "SAM build failed." }

    # SAM supports YAML parameter files but not JSON parameter files. JSON is a
    # valid YAML document, so copy the canonical configuration to a generated
    # .yaml path. This preserves JSON-valued settings exactly on Windows.
    New-Item -ItemType Directory -Path (Split-Path $generatedParameterFile) -Force | Out-Null
    Copy-Item -LiteralPath $parameterFile -Destination $generatedParameterFile -Force
    $overrides = @(
        "file://$generatedParameterFile",
        "GitCommit=$commit",
        "AppVersion=$version",
        "BuildTimestamp=$buildTimestamp"
    )
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
