import os, paramiko
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.137.100',username='root',password='Mind@123',timeout=20,allow_agent=False,look_for_keys=False)
cmd=r"""
AUTH=""
for f in /var/run/sddm/*; do [ -f "$f" ] && AUTH="$f" && break; done
export DISPLAY=:0 XAUTHORITY="$AUTH"

echo '=== kiosk log ==='
tail -n 25 /home/HwHiAiUser/jichuang/output/hdmi_kiosk.log 2>/dev/null

echo ''
echo '=== xwininfo root ==='
DISPLAY=:0 XAUTHORITY="$AUTH" xwininfo -root -tree 2>&1 | head -40

echo ''
echo '=== pgrep firefox ==='
pgrep -af firefox | head -5
"""
_,o,_=ssh.exec_command(cmd,timeout=45)
print(o.read().decode(errors='replace'))
ssh.close()
