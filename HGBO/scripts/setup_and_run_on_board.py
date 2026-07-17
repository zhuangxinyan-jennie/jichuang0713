import paramiko
import sys

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting...")
ssh.connect(HOST, username=USER, password=PWD, timeout=15)

cmd = (
    "cd /home/HwHiAiUser/HGBO && "
    "pip3 install -r requirements.txt -q && "
    "python3 scripts/run_dse.py --operator video_pre_fuse --num 10 --alg tpe --mode mock && "
    "cat dse_ds/video_pre_fuse/tpe/best_config.json"
)
print("Installing deps and running DSE (10 trials)...")
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
out = stdout.read().decode()
err = stderr.read().decode()
print(out[-3000:] if len(out) > 3000 else out)
if err:
    print("STDERR:", err[-2000:], file=sys.stderr)
code = stdout.channel.recv_exit_status()
print("Exit code:", code)
ssh.close()
