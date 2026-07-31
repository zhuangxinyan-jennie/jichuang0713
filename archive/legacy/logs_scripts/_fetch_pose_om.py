import paramiko
from pathlib import Path

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
OUT = Path(r"F:\jichuang2026\clean_0606\exports_for_teammate")
OUT.mkdir(parents=True, exist_ok=True)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
cmd = r"""bash -lc "find /home/HwHiAiUser -iname '*yolo11n_pose*' 2>/dev/null | head -80; find /home/HwHiAiUser -iname '*pose*640*' 2>/dev/null | head -80" """
_, stdout, _ = ssh.exec_command(cmd, timeout=60)
print(stdout.read().decode(errors="replace"))

# Always pull the existing OM so teammate at least has the binary currently used
remote_om = "/home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640.om"
local_om = OUT / "yolo11n_pose_640.om"
print(f"Downloading OM {remote_om} -> {local_om}")
sftp = ssh.open_sftp()
sftp.get(remote_om, str(local_om))
sftp.close()
ssh.close()
print(f"OM_OK bytes={local_om.stat().st_size}")
print(f"LOCAL_OM={local_om}")
