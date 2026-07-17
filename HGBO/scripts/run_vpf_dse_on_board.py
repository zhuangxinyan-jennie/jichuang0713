"""Upload HGBO and run VideoPreFuse device DSE (NPU) on 310B board."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import paramiko

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"
LOCAL_ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = "/home/HwHiAiUser/HGBO"
NUM_TRIALS = 50
ALG = "tpe"

UPLOAD_PATHS = [
    "operators/common",
    "operators/video_pre_fuse",
    "hgbo_optune",
    "config",
    "scripts/run_dse.py",
]


def upload_tree(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    if local.is_file():
        remote_dir = os.path.dirname(remote)
        parts = remote_dir.strip("/").split("/")
        cur = ""
        for p in parts:
            cur += "/" + p
            try:
                sftp.stat(cur)
            except FileNotFoundError:
                sftp.mkdir(cur)
        sftp.put(str(local), remote)
        print("  uploaded", local.name)
        return

    for item in local.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(local)
        remote_path = f"{remote}/{rel.as_posix()}"
        remote_dir = os.path.dirname(remote_path)
        parts = remote_dir.strip("/").split("/")
        cur = ""
        for p in parts:
            cur += "/" + p
            try:
                sftp.stat(cur)
            except FileNotFoundError:
                sftp.mkdir(cur)
        sftp.put(str(item), remote_path)
    print("  uploaded tree", local.name)


def run_cmd(ssh: paramiko.SSHClient, cmd: str, timeout: int = 7200) -> tuple[int, str, str]:
    print("\n>>>", cmd[:200])
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-6000:])
    if err and code != 0:
        print("STDERR:", err[-3000:])
    return code, out, err


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=15)
    sftp = ssh.open_sftp()

    print("=== Upload framework & video_pre_fuse ===")
    for rel in UPLOAD_PATHS:
        local = LOCAL_ROOT / rel
        remote = f"{REMOTE_ROOT}/{rel.replace(chr(92), '/')}"
        upload_tree(sftp, local, remote)
    sftp.close()

    smoke_cfg = {
        "split_axis": "H",
        "tile_h": 4,
        "tile_w": 32,
        "tile_len": 256,
        "buffer_num": 1,
    }
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/vpf_smoke.json", "w") as handle:
        handle.write(json.dumps(smoke_cfg))
    remote_script = f"""#!/bin/bash
set -e
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize
source {REMOTE_ROOT}/.venv/bin/activate
cd {REMOTE_ROOT}/operators/video_pre_fuse
python3 benchmark.py /tmp/vpf_smoke.json
"""
    with sftp.open("/tmp/run_vpf_dse.sh", "w") as handle:
        handle.write(remote_script.replace("\r\n", "\n"))
    sftp.close()
    ssh.exec_command("chmod +x /tmp/run_vpf_dse.sh")

    print("\n=== Smoke benchmark (NPU) ===")
    code, out, _ = run_cmd(ssh, "/bin/bash /tmp/run_vpf_dse.sh", timeout=180)
    if code != 0:
        print("[ERROR] Smoke benchmark failed, aborting DSE")
        ssh.close()
        raise SystemExit(1)

    print(f"\n=== DSE video_pre_fuse {ALG} device x{NUM_TRIALS} ===")
    dse_script = f"""#!/bin/bash
set -e
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize
source {REMOTE_ROOT}/.venv/bin/activate
cd {REMOTE_ROOT}
python scripts/run_dse.py --operator video_pre_fuse --num {NUM_TRIALS} --alg {ALG} --mode device --fresh
"""
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/run_vpf_dse_full.sh", "w") as handle:
        handle.write(dse_script.replace("\r\n", "\n"))
    sftp.close()
    ssh.exec_command("chmod +x /tmp/run_vpf_dse_full.sh")

    t0 = time.time()
    code, out, _ = run_cmd(ssh, "/bin/bash /tmp/run_vpf_dse_full.sh", timeout=7200)
    elapsed = time.time() - t0
    print(f"\nDSE finished in {elapsed:.1f}s, exit={code}")

    summary: dict = {
        "operator": "video_pre_fuse",
        "alg": ALG,
        "mode": "device",
        "num_trials": NUM_TRIALS,
        "exit_code": code,
        "elapsed_sec": round(elapsed, 1),
    }

    _, stdout, _ = ssh.exec_command(
        f"cat {REMOTE_ROOT}/dse_ds/video_pre_fuse/{ALG}/best_config.json 2>/dev/null"
    )
    best = stdout.read().decode()
    summary["best_config"] = json.loads(best) if best.strip() else None

    _, stdout, _ = ssh.exec_command(
        f"grep -l ascendc_npu {REMOTE_ROOT}/dse_ds/video_pre_fuse/{ALG}/script/benchmark_*.json 2>/dev/null | wc -l"
    )
    npu_count = stdout.read().decode().strip()
    _, stdout, _ = ssh.exec_command(
        f"ls {REMOTE_ROOT}/dse_ds/video_pre_fuse/{ALG}/script/benchmark_*.json 2>/dev/null | wc -l"
    )
    total_count = stdout.read().decode().strip()
    summary["benchmark_npu_count"] = npu_count
    summary["benchmark_total_count"] = total_count

    out_path = LOCAL_ROOT / "dse_ds" / "board_experiment_summary.json"
    existing = {}
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
    existing[f"video_pre_fuse/{ALG}/device_npu"] = summary
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n=== Summary ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("Saved:", out_path)

    print("\n=== Fetch benchmark records to local ===")
    fetch_dir = LOCAL_ROOT / "dse_ds" / "video_pre_fuse" / ALG
    script_dir = fetch_dir / "script"
    script_dir.mkdir(parents=True, exist_ok=True)
    sftp = ssh.open_sftp()
    remote_script = f"{REMOTE_ROOT}/dse_ds/video_pre_fuse/{ALG}/script"
    try:
        for name in sftp.listdir(remote_script):
            if name.startswith("benchmark_") and name.endswith(".json"):
                sftp.get(f"{remote_script}/{name}", str(script_dir / name))
        for fname in ["best_config.json", f"video_pre_fuse_{ALG}_device_dse.db"]:
            try:
                sftp.get(
                    f"{REMOTE_ROOT}/dse_ds/video_pre_fuse/{ALG}/{fname}",
                    str(fetch_dir / fname),
                )
            except FileNotFoundError:
                pass
    except FileNotFoundError as exc:
        print("Fetch warning:", exc)
    sftp.close()
    ssh.close()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
