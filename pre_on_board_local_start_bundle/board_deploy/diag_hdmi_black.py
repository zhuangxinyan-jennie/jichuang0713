# -*- coding: utf-8 -*-
import os, stat, paramiko
HOST=os.environ.get("BOARD_HOST","192.168.137.100")
cmd=r"""
AUTH=""
for f in /var/run/sddm/*; do [ -f "$f" ] && AUTH="$f" && break; done
export DISPLAY=:0 XAUTHORITY="$AUTH"

echo '=== PC frontend from board ==='
code=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 3 http://192.168.137.1:5173/ || echo fail)
echo HTTP_5173=$code

echo ''
echo '=== firefox window ==='
DISPLAY=:0 XAUTHORITY="$AUTH" xdotool search --onlyvisible --class Navigator 2>/dev/null | head -3 || echo no_xdotool_or_window
DISPLAY=:0 XAUTHORITY="$AUTH" wmctrl -l 2>/dev/null | head -5 || echo no_wmctrl

echo ''
echo '=== try screenshot ==='
if command -v import >/dev/null 2>&1; then
  DISPLAY=:0 XAUTHORITY="$AUTH" import -window root /tmp/hdmi_screen.png 2>&1
  ls -la /tmp/hdmi_screen.png 2>/dev/null
  python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/hdmi_screen.png')
if p.exists():
    data=p.read_bytes()
  # sample if mostly black
    try:
        from PIL import Image
        import io
        im=Image.open(io.BytesIO(data))
        px=im.convert('RGB').resize((64,64))
        vals=list(px.getdata())
        avg=sum(sum(c) for c in vals)/(len(vals)*3)
        dark=sum(1 for r,g,b in vals if r<20 and g<20 and b<20)/len(vals)
        print(f'screenshot_size={p.stat().st_size} avg_brightness={avg:.1f} dark_ratio={dark:.2f}')
    except Exception as e:
        print('pil_fail',e,'size',p.stat().st_size)
PY
else
  echo import_not_found
fi

echo ''
echo '=== drm connectors ==='
for f in /sys/class/drm/card*/status; do echo "$f: $(cat $f 2>/dev/null)"; done 2>/dev/null | head -10
"""
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username="root",password=os.environ.get("BOARD_PASS","Mind@123"),timeout=20,allow_agent=False,look_for_keys=False)
sftp=ssh.open_sftp()
with sftp.open('/tmp/hdmi_diag2.sh','w') as f: f.write(cmd)
sftp.chmod('/tmp/hdmi_diag2.sh', stat.S_IRUSR|stat.S_IWUSR|stat.S_IXUSR)
sftp.close()
_,o,e=ssh.exec_command('/bin/bash /tmp/hdmi_diag2.sh',timeout=90)
print(o.read().decode(errors='replace'))
err=e.read().decode(errors='replace').strip()
if err: print('ERR',err[-600:])
# try download screenshot
try:
    sftp=ssh.open_sftp()
    local=r'F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\logs\hdmi_screen.png'
    sftp.get('/tmp/hdmi_screen.png', local)
    sftp.close()
    print('saved', local)
except Exception as ex:
    print('no_screenshot', ex)
ssh.close()
