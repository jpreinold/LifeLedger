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

    $parameters = Get-Content -Raw $parameterFile | ConvertFrom-Json
    $overrides = @()
    foreach ($property in $parameters.PSObject.Properties) {
        $overrides += "$($property.Name)=$($property.Value)"
    }
    $commit = (git rev-parse HEAD).Trim()
    $version = (git describe --tags --always).Trim()
    $buildTimestamp = [DateTime]::UtcNow.ToString("o")
    $overrides += "GitCommit=$commit"
    $overrides += "AppVersion=$version"
    $overrides += "BuildTimestamp=$buildTimestamp"

    sam validate --lint --template-file $templateFile
    if ($LASTEXITCODE -ne 0) { throw "SAM validation failed." }
    sam build --template-file $templateFile
    if ($LASTEXITCODE -ne 0) { throw "SAM build failed." }
    sam deploy --config-file $configFile --config-env production --parameter-overrides $overrides
    if ($LASTEXITCODE -ne 0) { throw "SAM deployment failed." }
    & $python deploy\post_deploy_verify.py --stack-name lifeledger-api --expected-commit $commit
    if ($LASTEXITCODE -ne 0) { throw "Post-deployment verification failed." }
}
finally {
    Pop-Location
}
