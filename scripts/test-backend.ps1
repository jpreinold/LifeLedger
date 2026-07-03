$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$venvActivate = Join-Path $backendDir ".venv\Scripts\Activate.ps1"

Set-Location $backendDir

if (-not (Test-Path $venvActivate)) {
    Write-Error "Backend virtualenv not found at $venvActivate. Run: cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1; python -m pip install -r requirements.txt"
}

. $venvActivate
python -m pytest
