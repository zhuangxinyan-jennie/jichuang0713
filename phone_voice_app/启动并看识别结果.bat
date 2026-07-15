@echo off
chcp 65001 >nul
title 看板子识别结果（开 bridge）
cd /d "%~dp0"
echo.
echo 本窗口会显示：[bridge] partial: / final:
echo 请保持本窗口打开，再用手机 App 按住说话。
echo.
set BOARD_HOST=%PHONE_VOICE_BOARD_HOST%
if "%BOARD_HOST%"=="" set BOARD_HOST=192.168.137.100
pushd server
python -c "import aiohttp,numpy,cryptography" 2>nul
if errorlevel 1 python -m pip install -r requirements.txt
python bridge.py --board-host %BOARD_HOST%
popd
pause
