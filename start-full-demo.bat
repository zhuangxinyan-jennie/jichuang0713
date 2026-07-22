@echo off
setlocal
cd /d "%~dp0"
title Xiongda Full Demo
echo.
echo ========================================
echo   Xiongda Full Demo - starting...
echo ========================================
echo   Keep this window open.
echo   Browser will open http://127.0.0.1:5173
echo.
if not exist "%~dp0start-full-demo.ps1" (
  echo [ERROR] start-full-demo.ps1 not found in:
  echo   %cd%
  echo.
  pause
  exit /b 1
)
where powershell >nul 2>&1
if errorlevel 1 (
  echo [ERROR] powershell.exe not found
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-full-demo.ps1" %*
set ERR=%ERRORLEVEL%
echo.
if not "%ERR%"=="0" (
  echo [ERROR] start failed, exit code %ERR%
  echo Check logs under xiongda_app\logs\dev-stack
) else (
  echo Start finished.
)
echo To stop everything, run stop-full-demo.bat
echo.
pause
exit /b %ERR%
