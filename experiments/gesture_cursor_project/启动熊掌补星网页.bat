@echo off
chcp 65001 >nul
cd /d "%~dp0python"
set PORT=8770
echo 正在关闭旧的 %PORT% 端口服务（如有）...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
echo 正在启动「补全熊掌 + 手势光标」...
echo 浏览器会自动打开 http://127.0.0.1:%PORT%/paw-stars
echo 摄像头预览窗口按 ESC 退出。
"f:\jichuang2026\2026--\gesture_project\venv\Scripts\python.exe" run_paw_stars_demo.py --port %PORT%
pause
