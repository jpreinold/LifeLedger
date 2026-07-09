$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$tmpDir = Join-Path $repoRoot ".tmp"
$venvActivate = Join-Path $backendDir ".venv\Scripts\Activate.ps1"

New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
$env:TMP = $tmpDir
$env:TEMP = $tmpDir

Set-Location $backendDir

if (-not (Test-Path $venvActivate)) {
    Write-Error "Backend virtualenv not found at $venvActivate. Run: cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1; python -m pip install -r requirements.txt"
}

. $venvActivate
$pytestTemp = Join-Path $tmpDir ("pytest-" + [guid]::NewGuid().ToString("N"))
python -m pytest --basetemp $pytestTemp

Set-Location $frontendDir
npm.cmd run build

$package = Get-Content -Raw -LiteralPath (Join-Path $frontendDir "package.json") | ConvertFrom-Json
if ($package.scripts.PSObject.Properties.Name -contains "lint") {
    npm.cmd run lint
}
