@echo off
chcp 65001 >nul
title PC识别终端 18084（手机直连板子时用）
cd /d "%~dp0server"
echo 手机直连板子时，识别结果会镜像到本窗口（18084）
python pc_asr_mirror_terminal.py
pause
