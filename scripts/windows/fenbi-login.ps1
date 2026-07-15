[CmdletBinding()]
param(
    [switch]$Auto,
    [switch]$Headless,
    [ValidateRange(1, 3600)]
    [int]$Timeout = 180
)

. (Join-Path $PSScriptRoot "common.ps1")

$arguments = @("auth", "fenbi-login", "--timeout", $Timeout.ToString())
if (-not $Auto) {
    $arguments += "--manual"
}
if (-not $Headless) {
    $arguments += "--headed"
}

Invoke-ExamDb -Arguments $arguments
