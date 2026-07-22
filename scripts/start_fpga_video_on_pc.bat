@echo off
cd /d F:\jichuang2026\clean_0606
python scripts\recv_udp_video.py --bind 192.168.137.1 --port 1234 --width 1280 --height 720 --display --display-mode fit --no-save --timeout 86400
pause
