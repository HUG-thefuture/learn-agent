@echo off
rem learn-agent smart launcher (double-click) -- desktop GUI mode
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
rem The launcher starts the GUI with pythonw (no console) and returns at once.
"%PY%" launch.py gui
if errorlevel 1 (
  echo.
  echo Startup reported a problem. See data\logs\gui_error.log
  pause
)
