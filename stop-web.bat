@echo off
rem learn-agent Web console stopper (double-click). ASCII only.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-web.ps1"
ping -n 3 127.0.0.1 >nul
