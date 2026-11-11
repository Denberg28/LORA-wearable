@echo off
cd /d "%~dp0"
py -3 -m monitor.app %*
if errorlevel 1 pause
