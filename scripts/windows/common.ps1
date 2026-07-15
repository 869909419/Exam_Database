Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Get-ExamDbPython {
    $candidate = Join-Path $script:ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $candidate)) {
        throw "Python virtual environment not found. Run scripts/windows/bootstrap.ps1 first."
    }
    return $candidate
}

function Invoke-ExamDb {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $python = Get-ExamDbPython
    Push-Location $script:ProjectRoot
    try {
        & $python -m examdb @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "examdb exited with code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

function Import-ExamDbLocalEnv {
    $envFile = Join-Path $script:ProjectRoot "scripts\obsidian\.env.local"
    if (-not (Test-Path $envFile)) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $envFile -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        if ($trimmed -notmatch '^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            continue
        }

        $name = $Matches[1]
        $value = $Matches[2].Trim()
        if ($value.Length -ge 2) {
            $doubleQuoted = $value.StartsWith('"') -and $value.EndsWith('"')
            $singleQuoted = $value.StartsWith("'") -and $value.EndsWith("'")
            if ($doubleQuoted -or $singleQuoted) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        if (-not (Test-Path "Env:$name")) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}
