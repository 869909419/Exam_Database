[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Source,
    [string]$Since,
    [ValidateRange(1, 10000)]
    [int]$Limit,
    [switch]$Refresh,
    [string]$Profile,
    [string]$Keywords
)

. (Join-Path $PSScriptRoot "common.ps1")

$arguments = @("ingest", "articles", "--source", $Source)
if ($Since) {
    $arguments += @("--since", $Since)
}
if ($PSBoundParameters.ContainsKey("Limit")) {
    $arguments += @("--limit", $Limit.ToString())
}
if ($Refresh) {
    $arguments += "--refresh"
}
if ($Profile) {
    $arguments += @("--profile", $Profile)
}
if ($Keywords) {
    $arguments += @("--keywords", $Keywords)
}

Invoke-ExamDb -Arguments $arguments
