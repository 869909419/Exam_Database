[CmdletBinding()]
param(
    [string]$BindHost = "127.0.0.1",
    [ValidateRange(1, 65535)]
    [int]$Port = 8765,
    [switch]$NoBrowser
)

. (Join-Path $PSScriptRoot "common.ps1")
$python = Get-ExamDbPython
$url = "http://${BindHost}:${Port}"
$arguments = @("-m", "examdb", "practice", "serve", "--host", $BindHost, "--port", $Port.ToString())

Write-Host "ExamDB practice UI: $url"
$server = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $script:ProjectRoot -NoNewWindow -PassThru

try {
    if (-not $NoBrowser) {
        $ready = $false
        for ($attempt = 0; $attempt -lt 40; $attempt++) {
            if ($server.HasExited) {
                break
            }
            try {
                Invoke-WebRequest -Uri "$url/api/metadata" -UseBasicParsing -TimeoutSec 1 | Out-Null
                $ready = $true
                break
            }
            catch {
                Start-Sleep -Milliseconds 250
            }
        }
        if ($ready) {
            Start-Process $url
        }
        else {
            Write-Warning "The server did not become ready in time. Open $url manually after checking its output."
        }
    }

    Wait-Process -Id $server.Id
    $server.Refresh()
    if ($server.ExitCode -ne 0) {
        throw "Practice server exited with code $($server.ExitCode)"
    }
}
finally {
    if (-not $server.HasExited) {
        Stop-Process -Id $server.Id -Force
    }
}
