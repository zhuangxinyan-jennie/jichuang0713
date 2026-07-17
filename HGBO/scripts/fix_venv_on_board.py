"""补传 tomli 并在板子 venv 中离线安装依赖."""
import paramiko

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"
WHEELS = [
    "tomli-2.4.1-py3-none-any.whl",
    "importlib_metadata-8.7.1-py3-none-any.whl",
    "zipp-3.23.1-py3-none-any.whl",
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
for name in WHEELS:
    local = rf"F:\jichuang2026\HGBO\wheels_linux\{name}"
    remote = f"/home/HwHiAiUser/HGBO/wheels_linux/{name}"
    sftp.put(local, remote)
    print("uploaded", name)
sftp.close()

cmd = (
    "bash -lc '"
    "cd /home/HwHiAiUser/HGBO && "
    "source .venv/bin/activate && "
    "pip install --no-index --find-links=wheels_linux -r requirements.txt && "
    "python -c \"import optuna; print(\\\"optuna OK\\\", optuna.__version__)\""
    "'"
)
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err[-1000:])
print("exit", stdout.channel.recv_exit_status())
ssh.close()
