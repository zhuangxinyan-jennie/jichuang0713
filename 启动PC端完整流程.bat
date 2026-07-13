@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ===== clean_0606 项目启动 =====
echo 目录: %~dp0
echo.
echo 首次请先运行: powershell -File setup-env.ps1
echo 没装 CosyVoice 模型时可: start-pc-stack.ps1 -SkipTts
echo.
echo   1. Bear Agent   http://127.0.0.1:8765
echo   2. CosyVoice    http://127.0.0.1:9890
echo   3. 前端页面     http://127.0.0.1:5173
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-pc-stack.ps1" %*
if errorlevel 1 pause
