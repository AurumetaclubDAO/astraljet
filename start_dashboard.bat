@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dashboard_start.ps1"
exit /b %errorlevel%
