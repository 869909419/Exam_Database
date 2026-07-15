[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot "common.ps1")
Invoke-ExamDb -Arguments @("report", "weekly")
