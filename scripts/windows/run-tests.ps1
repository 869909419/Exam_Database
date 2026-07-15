[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot "common.ps1")
$python = Get-ExamDbPython

Push-Location $script:ProjectRoot
try {
    & $python -m unittest discover -s tests
    if ($LASTEXITCODE -ne 0) {
        throw "Tests failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
