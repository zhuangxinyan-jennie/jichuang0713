@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-full-demo.ps1" %*
exit /b %ERRORLEVEL%
