@echo off
setlocal
cd /d "%~dp0"
title Xiongda Full Demo - STOP
echo.
echo ========================================
echo   Stopping Xiongda Full Demo...
echo ========================================
echo.
if not exist "%~dp0stop-full-demo.ps1" (
  echo [ERROR] stop-full-demo.ps1 not found
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-full-demo.ps1" %*
echo.
pause
