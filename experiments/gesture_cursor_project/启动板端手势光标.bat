@echo off
chcp 65001 >nul
title 板端手势光标 landmarks :8770（无 MediaPipe）
cd /d "%~dp0"

echo.
echo === 2D 地图手势光标：板载摄像头 + NPU（不用 PC 摄像头 / MediaPipe）===
echo.
echo 前提：
echo   1) 板子已开视觉运行时（BOARD_LOCAL_CAMERA=1）
echo   2) PC 已开 board_bridge 听 18082（会写 latest_hand_landmarks.json）
echo.
echo 若已用  run_all.py --bear-bridge ，桥接进程已自带 :8770，可跳过本窗口。
echo 本窗口仅在「只有落盘文件、缺 8770」时用。
echo.
echo 前端: cd xiongda_app ^&^& npm run dev
echo 浏览器地图页 → 2D地图 → 对着板子摄像头举手/捏合
echo.

set ROOT=%~dp0..
set PY=%ROOT%\bear_agent\.venv\Scripts\python.exe
if not exist "%PY%" set PY=%ROOT%\.venv\Scripts\python.exe
if not exist "%PY%" set PY=python

cd /d "%ROOT%\bear_agent"
"%PY%" -m board_bridge.serve_board_landmarks --port 8770
pause
