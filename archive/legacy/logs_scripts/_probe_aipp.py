import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=12)

remote_py = r'''
from pathlib import Path
print("=== models_om ===")
p = Path("/home/HwHiAiUser/pre_on_board/models_om")
if p.exists():
    for x in sorted(p.iterdir()):
        if x.is_file():
            print(f"{x.name}\t{x.stat().st_size}")
else:
    print("MISSING models_om")

print("=== find aipp files ===")
root = Path("/home/HwHiAiUser/pre_on_board")
hits = list(root.rglob("*aipp*")) + list(root.rglob("*AIPP*"))
for h in hits[:40]:
    print(h)
if not hits:
    print("(none)")

print("=== grep aipp in scripts ===")
import re
pat = re.compile(r"aipp", re.I)
count = 0
for folder in [root/"board_deploy", root/"motion"]:
    if not folder.exists():
        continue
    for f in folder.rglob("*"):
        if f.suffix.lower() not in {".py", ".sh", ".cfg", ".config", ".ini", ".txt", ".md"}:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if pat.search(text):
            for i, line in enumerate(text.splitlines(), 1):
                if pat.search(line):
                    print(f"{f}:{i}:{line.strip()[:160]}")
                    count += 1
                    if count >= 30:
                        break
        if count >= 30:
            break
if count == 0:
    print("(no aipp mentions in board_deploy/motion)")

print("=== InferSession IO ===")
try:
    from ais_bench.infer.interface import InferSession
except Exception as e:
    print("InferSession unavailable:", e)
    raise SystemExit(0)

for name in ["yolo11n_pose_640.om", "yolo_face_hand_person.om", "yolo11n_pose_320.om"]:
    om = p / name
    if not om.exists():
        print(name, "MISSING")
        continue
    try:
        s = InferSession(0, str(om))
        ins = s.get_inputs()
        outs = s.get_outputs()
        print("===", name, "===")
        for i, x in enumerate(ins):
            print(" in", i, getattr(x, "name", None), getattr(x, "shape", None), getattr(x, "datatype", None))
        print(" n_in", len(ins), "n_out", len(outs))
    except Exception as e:
        print(name, "OPEN_FAIL", type(e).__name__, e)
'''

sftp = c.open_sftp()
with sftp.file("/tmp/probe_aipp_om.py", "w") as f:
    f.write(remote_py)
sftp.close()

cmd = "bash -lc 'source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null; /usr/local/miniconda3/bin/python3 /tmp/probe_aipp_om.py'"
_, stdout, stderr = c.exec_command(cmd, timeout=120)
print(stdout.read().decode("utf-8", "replace"))
err = stderr.read().decode("utf-8", "replace")
if err.strip():
    print("STDERR:", err[:2500])
c.close()
