"""Check DSE progress and NPU backend ratio on board."""
import json
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
HGBO = "/home/HwHiAiUser/HGBO"
DSE = f"{HGBO}/dse_ds/video_pre_fuse/tpe"

REMOTE = f"""#!/bin/bash
echo '=== process ==='
ps aux | grep 'run_dse.py' | grep -v grep || echo DONE

echo '=== optuna ==='
source {HGBO}/.venv/bin/activate
cd {HGBO}
python3 /tmp/summarize_dse.py

echo '=== best_config ==='
cat {DSE}/best_config.json 2>/dev/null || echo not_yet
"""

SUMMARY_PY = f"""
import glob, json, os, optuna
from datetime import datetime

db = "sqlite:///{DSE}/video_pre_fuse_tpe_device_dse.db"
study = optuna.load_study(study_name="video_pre_fuse_tpe_device_dse", storage=db)
states = {{}}
for t in study.trials:
    states[t.state.name] = states.get(t.state.name, 0) + 1
running = [t.number for t in study.trials if t.state.name == "RUNNING"]
complete = [t for t in study.trials if t.state.name == "COMPLETE" and t.value is not None and t.value < 1e7]
print("trials_total:", len(study.trials))
print("states:", states)
print("running_trial:", running[:3] if running else "none")
if complete:
    best = min(complete, key=lambda t: t.value)
    print("best_trial:", best.number, "latency_ms:", round(best.value, 4), "params:", best.params)

files = sorted(glob.glob("{DSE}/script/benchmark_*.json"), key=os.path.getmtime)
# only files touched during this device run (Apr 9 2026 on board clock)
recent = []
for f in files:
    mtime = datetime.fromtimestamp(os.path.getmtime(f))
    try:
        d = json.load(open(f))
        cs = d.get("metrics", {{}}).get("compile_status", "?")
        lat = d.get("metrics", {{}}).get("latency_ms")
        trial = os.path.basename(f).replace("benchmark_", "").replace(".json", "")
        recent.append((trial, cs, lat, mtime.strftime("%m-%d %H:%M")))
    except Exception:
        pass

npu = [r for r in recent if "npu" in str(r[1]).lower() or r[1] == "aclnn_npu"]
mock = [r for r in recent if r[1] == "mock_success"]
python_fb = [r for r in recent if "python" in str(r[1]).lower()]
print("benchmark_files:", len(recent))
print("npu_records:", len(npu))
print("mock_stale_or_other:", len(mock))
print("python_fallback:", len(python_fb))
print("latest_5:")
for row in recent[-5:]:
    print(" ", row)
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/summarize_dse.py", "w") as f:
    f.write(SUMMARY_PY)
with sftp.open("/tmp/probe_now.sh", "w") as f:
    f.write(REMOTE)
sftp.close()
_, stdout, stderr = ssh.exec_command("bash /tmp/probe_now.sh", timeout=60)
print(stdout.read().decode(errors="replace"))
e = stderr.read().decode(errors="replace")
if e.strip():
    print("STDERR:", e[-1500:])
ssh.close()
