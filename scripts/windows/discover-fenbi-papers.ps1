[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$LabelId,
    [ValidateSet("xingce", "shenlun")]
    [string]$PaperKind = "xingce",
    [ValidateRange(1, 500)]
    [int]$PageSize = 50,
    [switch]$Headed,
    [ValidateRange(1, 3600)]
    [int]$Timeout = 180
)

. (Join-Path $PSScriptRoot "common.ps1")

$arguments = @(
    "discover", "fenbi-papers",
    "--label-id", $LabelId,
    "--paper-kind", $PaperKind,
    "--page-size", $PageSize.ToString(),
    "--timeout", $Timeout.ToString()
)
if ($Headed) {
    $arguments += "--headed"
}

Invoke-ExamDb -Arguments $arguments
