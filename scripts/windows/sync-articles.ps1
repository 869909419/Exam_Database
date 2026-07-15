[CmdletBinding()]
param(
    [string]$Source,
    [string]$Since,
    [ValidateRange(1, 10000)]
    [int]$Limit,
    [string]$Path,
    [switch]$OnlyChanged,
    [switch]$Apply
)

. (Join-Path $PSScriptRoot "common.ps1")

$arguments = @("sync", "articles")
if ($Source) {
    $arguments += @("--source", $Source)
}
if ($Since) {
    $arguments += @("--since", $Since)
}
if ($PSBoundParameters.ContainsKey("Limit")) {
    $arguments += @("--limit", $Limit.ToString())
}
if ($Path) {
    $arguments += @("--path", $Path)
}
if ($OnlyChanged) {
    $arguments += "--only-changed"
}
if ($Apply) {
    $arguments += "--apply"
}

Invoke-ExamDb -Arguments $arguments
