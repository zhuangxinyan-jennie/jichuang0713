@echo off
chcp 65001 >nul
title Phone Voice Bridge
cd /d "%~dp0"

set BOARD_HOST=%PHONE_VOICE_BOARD_HOST%
if "%BOARD_HOST%"=="" set BOARD_HOST=192.168.137.100

echo.
echo === Phone Voice：手机流式语音 → 板端 ASR ===
echo 板子 IP: %BOARD_HOST%
echo 手机请用 HTTPS 打开（例 https://电脑IP:8788/）
echo 识别结果会显示在本黑窗口
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo 未找到 python
  pause
  exit /b 1
)

pushd server
python -c "import aiohttp,numpy,cryptography" 2>nul
if errorlevel 1 (
  echo 安装依赖...
  python -m pip install -r requirements.txt
)
python bridge.py --board-host %BOARD_HOST%
popd
pause
