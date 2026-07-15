@echo off
chcp 65001 >nul
title 2D地图手势光标服务 (端口 8770)
cd /d "%~dp0"

echo.
echo === 2D 地图手势演示（仅本机摄像头，不开板端）===
echo 1) 本窗口会启动 MediaPipe 手部关键点服务 :8770
echo 2) 请另开终端启动前端:  cd xiongda_app ^&^& npm run dev
echo 3) 浏览器打开 http://127.0.0.1:5173  → 点顶栏「地图查询」
echo 4) 右下角点「2D地图」放大；举手移动光标，捏合点星星
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
