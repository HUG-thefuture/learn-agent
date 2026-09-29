@echo off
rem learn-agent 桌面版启动器（双击运行）
cd /d %~dp0
set PYW=C:\Users\Niko\AppData\Local\Programs\Python\Python311\pythonw.exe
if not exist "%PYW%" set PYW=pythonw
start "learn-agent GUI" "%PYW%" gui\app.py
