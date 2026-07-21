import os, stat, paramiko
from pathlib import Path
HOST='192.168.137.100'
local=Path(__file__).resolve().parents[1]/'jichuang'/'ensure_hdmi_display.sh'
remote='/home/HwHiAiUser/jichuang/ensure_hdmi_display.sh'
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username='root',password='Mind@123',timeout=20,allow_agent=False,look_for_keys=False)
sftp=ssh.open_sftp()
with open(local,'rb') as f: data=f.read()
with sftp.open(remote,'wb') as rf: rf.write(data)
sftp.chmod(remote, stat.S_IRUSR|stat.S_IWUSR|stat.S_IXUSR)
sftp.close(); ssh.close()
print('uploaded', remote)
