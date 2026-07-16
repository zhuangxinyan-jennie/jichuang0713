@echo off
chcp 65001 >nul
title 【旧】本机 MediaPipe 手势 :8770
cd /d "%~dp0"

echo.
echo === 【旧方案】本机摄像头 + MediaPipe（仅离线调试）===
echo 交付演示请改用：启动板端手势光标.bat
echo   或直接开 run_all.py --bear-bridge（已含 :8770）
echo.
echo 预览窗按 ESC 退出本服务
echo.

set GESTURE_CURSOR_PORT=8770
if exist "python\run_paw_stars_demo.py" (
  cd python
  where python >nul 2>&1
  if errorlevel 1 (
    echo 未找到 python，请先安装 Python 或使用 gesture_cursor_project 的 .venv
    pause
    exit /b 1
  )
  if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" run_paw_stars_demo.py --port 8770 --no-browser
  ) else (
    python run_paw_stars_demo.py --port 8770 --no-browser
  )
) else (
  echo 找不到 python\run_paw_stars_demo.py
  pause
  exit /b 1
)
pause
