# learn-agent Web console stopper.
# Delegates to launch.py stop, which kills the registered instance and any
# process still holding the port (stale servers, instances started by hand).
$ErrorActionPreference = 'SilentlyContinue'
Set-Location -Path $PSScriptRoot

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $py) {
    Write-Host "ERROR: Python not found on PATH."
    exit 1
}

& $py launch.py stop
