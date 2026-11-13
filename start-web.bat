@echo off
rem learn-agent smart launcher (double-click) -- Web console mode
rem Detects the on-disk code version; if a stale instance is running it is
rem restarted automatically, otherwise the running one is reused.
rem All ASCII on purpose: cmd decodes .bat as GBK, so Chinese would break parsing.
cd /d "%~dp0"

set "PY=python"
where python >nul 2>&1 && goto have
set "PY=py"
where py >nul 2>&1 && goto have
echo Python not found on PATH. Install Python 3 and retry.
pause
exit /b 1

:have
"%PY%" launch.py web
if errorlevel 1 (
  echo.
  echo Startup reported a problem. See data\server.err.log
  pause
)
