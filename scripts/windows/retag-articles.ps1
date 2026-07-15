[CmdletBinding()]
param(
    [string]$Source,
    [string]$Since,
    [ValidateRange(1, 10000)]
    [int]$Limit,
    [string]$Path,
    [switch]$OnlyNeedsReview,
    [switch]$Apply
)

. (Join-Path $PSScriptRoot "common.ps1")
Import-ExamDbLocalEnv

$arguments = @("retag", "articles")
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
if ($OnlyNeedsReview) {
    $arguments += "--only-needs-review"
}
if ($Apply) {
    $arguments += "--apply"
}

Invoke-ExamDb -Arguments $arguments
