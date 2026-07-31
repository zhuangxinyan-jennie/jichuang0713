@echo off
setlocal
cd /d "%~dp0"
title Xiongda Full Demo - STOP
echo.
echo ========================================
echo   Stopping Xiongda Full Demo...
echo ========================================
echo.
echo [TIP] Do NOT click/drag in this black window while running.
echo       If title shows "Select" and it freezes, press ENTER once.
echo       勿用鼠标选中黑窗口文字；若标题出现「选择」卡住，按 Enter 继续。
echo.
if not exist "%~dp0stop-full-demo.ps1" (
  echo [ERROR] stop-full-demo.ps1 not found
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-full-demo.ps1" %*
echo.
pause
