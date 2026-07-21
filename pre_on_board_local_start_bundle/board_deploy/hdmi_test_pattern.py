# -*- coding: utf-8 -*-
"""Paint test pattern on board HDMI to verify physical output."""
import os, stat, paramiko
HOST=os.environ.get("BOARD_HOST","192.168.137.100")
REMOTE=r"""
AUTH=""
for f in /var/run/sddm/*; do [ -f "$f" ] && AUTH="$f" && break; done
export DISPLAY=:0 XAUTHORITY="$AUTH"

DISPLAY=:0 XAUTHORITY="$AUTH" xset dpms force on
DISPLAY=:0 XAUTHORITY="$AUTH" xset -dpms
DISPLAY=:0 XAUTHORITY="$AUTH" xset s off
DISPLAY=:0 XAUTHORITY="$AUTH" xrandr --output VGA-1 --mode 1920x1080 --primary 2>/dev/null || true

# 纯蓝底 + 白字，肉眼应能看见
DISPLAY=:0 XAUTHORITY="$AUTH" xsetroot -solid '#1565C0' 2>/dev/null || true
if command -v xmessage >/dev/null 2>&1; then
  DISPLAY=:0 XAUTHORITY="$AUTH" xmessage -center -timeout 30 'HDMI 测试：若你能看到蓝底白字，说明显示正常' 2>/dev/null &
fi
echo '[TEST] blue screen + message for 30s on VGA-1'
sleep 2
DISPLAY=:0 XAUTHORITY="$AUTH" xrandr --query | head -6
"""
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username='root',password=os.environ.get('BOARD_PASS','Mind@123'),timeout=20,allow_agent=False,look_for_keys=False)
sftp=ssh.open_sftp()
with sftp.open('/tmp/hdmi_test_pattern.sh','w') as f: f.write(REMOTE)
sftp.chmod('/tmp/hdmi_test_pattern.sh', stat.S_IRUSR|stat.S_IWUSR|stat.S_IXUSR)
sftp.close()
_,o,e=ssh.exec_command('/bin/bash /tmp/hdmi_test_pattern.sh',timeout=45)
print(o.read().decode(errors='replace'))
ssh.close()
