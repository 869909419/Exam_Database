[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PaperId,
    [switch]$Shenlun,
    [switch]$Import,
    [switch]$Headed,
    [ValidateRange(1, 3600)]
    [int]$Timeout = 180
)

. (Join-Path $PSScriptRoot "common.ps1")

$arguments = @("fetch", "fenbi-solution", "--paper-id", $PaperId, "--timeout", $Timeout.ToString())
if ($Shenlun) {
    $arguments += "--shenlun"
}
if ($Import) {
    $arguments += "--import"
}
if ($Headed) {
    $arguments += "--headed"
}

Invoke-ExamDb -Arguments $arguments
