@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
echo.
echo NPU ctc_om vs CPU ctc benchmark
echo Close other 18083 listeners first. Speak to board mic during each round.
echo.
python pre_on_board_local_start_bundle\board_deploy\probe_ctc_npu_vs_cpu.py --duration 30
pause
