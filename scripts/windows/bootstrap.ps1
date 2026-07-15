[CmdletBinding()]
param(
    [switch]$SkipPlaywright
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

function Assert-LastExitCode {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

Push-Location $projectRoot
try {
    if (-not (Test-Path $venvPython)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3.11 -m venv .venv
        }
        elseif (Get-Command python -ErrorAction SilentlyContinue) {
            & python -m venv .venv
        }
        else {
            throw "Python 3.11+ was not found. Install Python and enable the py launcher."
        }
        Assert-LastExitCode "Creating the virtual environment"
    }

    & $venvPython -c "import sys; assert sys.version_info >= (3, 11), sys.version"
    Assert-LastExitCode "Checking Python version"

    & $venvPython -m pip install --upgrade pip
    Assert-LastExitCode "Upgrading pip"

    & $venvPython -m pip install -e .
    Assert-LastExitCode "Installing ExamDB"

    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm was not found. Install the current Node.js LTS release."
    }

    & npm ci
    Assert-LastExitCode "Installing Node.js dependencies"

    if (-not $SkipPlaywright) {
        & npx playwright install chromium
        Assert-LastExitCode "Installing Playwright Chromium"
    }

    Write-Host "ExamDB Windows environment is ready."
    Write-Host "Next: powershell -ExecutionPolicy Bypass -File scripts/windows/run-tests.ps1"
}
finally {
    Pop-Location
}
