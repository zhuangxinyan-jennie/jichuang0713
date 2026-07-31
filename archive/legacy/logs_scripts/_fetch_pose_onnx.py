import paramiko
from pathlib import Path

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
OUT_DIR = Path(r"F:\jichuang2026\clean_0606\exports_for_teammate")
OUT_DIR.mkdir(parents=True, exist_ok=True)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)

find_cmd = r"""bash -lc "find /home/HwHiAiUser -iname '*yolo11n_pose*.onnx' 2>/dev/null; ls -lah /home/HwHiAiUser/pre_on_board/pose_models 2>/dev/null; ls -lah /home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640* 2>/dev/null" """
_, stdout, _ = ssh.exec_command(find_cmd, timeout=60)
listing = stdout.read().decode(errors="replace")
print("=== board search ===")
print(listing)

candidates = []
for line in listing.splitlines():
    line = line.strip()
    if line.endswith(".onnx") and "yolo11n_pose" in line.lower():
        candidates.append(line)

# Prefer exact 640
preferred = [p for p in candidates if "640" in Path(p).name]
pick = preferred[0] if preferred else (candidates[0] if candidates else None)
if not pick:
    print("NO_ONNX_FOUND")
    ssh.close()
    raise SystemExit(2)

local_path = OUT_DIR / Path(pick).name
print(f"Downloading: {pick} -> {local_path}")
sftp = ssh.open_sftp()
sftp.get(pick, str(local_path))
sftp.close()
ssh.close()
print(f"OK size={local_path.stat().st_size} bytes")
print(f"LOCAL={local_path}")
