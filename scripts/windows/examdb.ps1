[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$ExamDbArguments
)

. (Join-Path $PSScriptRoot "common.ps1")

if (-not $ExamDbArguments -or $ExamDbArguments.Count -eq 0) {
    $ExamDbArguments = @("--help")
}

Invoke-ExamDb -Arguments $ExamDbArguments
