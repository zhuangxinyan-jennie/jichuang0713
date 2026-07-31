"""离线安装依赖并在板子上跑 DSE."""
import paramiko
import sys
import os

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"
LOCAL_ZIP = r"F:\jichuang2026\HGBO\wheels_linux.zip"
REMOTE_ZIP = "/home/HwHiAiUser/HGBO/wheels_linux.zip"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting...")
ssh.connect(HOST, username=USER, password=PWD, timeout=15)

print("Uploading wheels_linux.zip (~80MB)...")
sftp = ssh.open_sftp()
sftp.put(LOCAL_ZIP, REMOTE_ZIP)
sftp.close()
print("Upload done.")

cmd = """
cd /home/HwHiAiUser/HGBO
mkdir -p wheels_linux
unzip -o wheels_linux.zip -d wheels_linux
source .venv/bin/activate
pip install --no-index --find-links=wheels_linux -r requirements.txt
python3 -c "import optuna; print('optuna OK', optuna.__version__)"
python3 scripts/run_dse.py --operator video_pre_fuse --num 10 --alg tpe --mode mock
echo '=== best_config ==='
cat dse_ds/video_pre_fuse/tpe/best_config.json
"""

print("Installing offline and running DSE...")
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=600)
out = stdout.read().decode()
err = stderr.read().decode()
print(out[-4000:] if len(out) > 4000 else out)
if err:
    print("STDERR:", err[-1500:], file=sys.stderr)
print("Exit:", stdout.channel.recv_exit_status())
ssh.close()
