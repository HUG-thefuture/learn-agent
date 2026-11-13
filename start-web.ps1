# learn-agent Web console launcher (double-click start-web.bat).
# Delegates to launch.py, which fingerprints the source tree, compares it with
# the registered running instance, and restarts only when the code actually
# changed. Kept for users who call the .ps1 directly.
$ErrorActionPreference = 'SilentlyContinue'
Set-Location -Path $PSScriptRoot

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $py) {
    Write-Host "ERROR: Python not found on PATH. Install Python 3 and retry."
    Read-Host "Press Enter to exit"
    exit 1
}

& $py launch.py web
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Startup reported a problem. See data\server.err.log"
    Read-Host "Press Enter to exit"
}
Start-Sleep -Seconds 2
