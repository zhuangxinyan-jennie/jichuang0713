"""上传算子并在 310B 板子上跑 device DSE 实验."""

from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path

import paramiko

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"
LOCAL_ROOT = Path(r"F:\jichuang2026\HGBO")
REMOTE_ROOT = "/home/HwHiAiUser/HGBO"

UPLOAD_PATHS = [
    "operators/common",
    "operators/video_pre_fuse",
    "operators/keypoint_post_process",
    "hgbo_optune",
    "config",
    "scripts/run_dse.py",
]

EXPERIMENTS = [
    ("video_pre_fuse", "tpe", 20),
    ("video_pre_fuse", "random", 20),
    ("keypoint_post_process", "tpe", 20),
    ("keypoint_post_process", "random", 20),
]


def upload_tree(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    if local.is_file():
        remote_dir = os.path.dirname(remote)
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            parts = remote_dir.strip("/").split("/")
            cur = ""
            for p in parts:
                cur += "/" + p
                try:
                    sftp.stat(cur)
                except FileNotFoundError:
                    sftp.mkdir(cur)
        sftp.put(str(local), remote)
        print("  uploaded", local.name, "->", remote)
        return

    for item in local.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(local)
        remote_path = f"{remote}/{rel.as_posix()}"
        remote_dir = os.path.dirname(remote_path)
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            parts = remote_dir.strip("/").split("/")
            cur = ""
            for p in parts:
                cur += "/" + p
                try:
                    sftp.stat(cur)
                except FileNotFoundError:
                    sftp.mkdir(cur)
        sftp.put(str(item), remote_path)
    print("  uploaded tree", local, "->", remote)


def chmod_scripts(ssh: paramiko.SSHClient) -> None:
    for sh in [
        f"{REMOTE_ROOT}/operators/video_pre_fuse/run_benchmark.sh",
        f"{REMOTE_ROOT}/operators/keypoint_post_process/run_benchmark.sh",
    ]:
        ssh.exec_command(f"chmod +x {sh}")


def run_cmd(ssh: paramiko.SSHClient, cmd: str, timeout: int = 3600) -> tuple[int, str, str]:
    print("\n>>>", cmd)
    stdin, stdout, stderr = ssh.exec_command(f"bash -lc '{cmd}'", timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-4000:])
    if err and code != 0:
        print("STDERR:", err[-2000:])
    return code, out, err


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=15)
    sftp = ssh.open_sftp()

    print("=== Upload operators & framework ===")
    for rel in UPLOAD_PATHS:
        local = LOCAL_ROOT / rel
        remote = f"{REMOTE_ROOT}/{rel.replace(chr(92), '/')}"
        if local.is_dir():
            upload_tree(sftp, local, remote)
        elif local.is_file():
            upload_tree(sftp, local, remote)

    sftp.close()
    chmod_scripts(ssh)
    run_cmd(
        ssh,
        f"sed -i 's/\\r$//' {REMOTE_ROOT}/operators/*/run_benchmark.sh 2>/dev/null; true",
        timeout=30,
    )

    print("\n=== Smoke test benchmarks ===")
    run_cmd(
        ssh,
        f"cd {REMOTE_ROOT} && python3 -c \"import json; json.dump({{"
        f"'split_axis':'H','tile_h':8,'blockDim':1,'buffer_num':1,"
        f"'pipeline_mode':'normal','align_policy':'relaxed'}}, "
        f"open('/tmp/vpf_smoke.json','w'))\" && "
        f"bash operators/video_pre_fuse/run_benchmark.sh /tmp/vpf_smoke.json | tail -8",
        timeout=180,
    )

    summary = {}
    for operator, alg, num in EXPERIMENTS:
        key = f"{operator}/{alg}/device"
        print(f"\n=== DSE {operator} {alg} device x{num} ===")
        cmd = (
            f"cd {REMOTE_ROOT} && source .venv/bin/activate && "
            f"python scripts/run_dse.py --operator {operator} --num {num} "
            f"--alg {alg} --mode device --fresh"
        )
        t0 = time.time()
        code, out, _ = run_cmd(ssh, cmd, timeout=3600)
        elapsed = time.time() - t0
        summary[key] = {"exit_code": code, "elapsed_sec": round(elapsed, 1)}

        stdin, stdout, stderr = ssh.exec_command(
            f"cat {REMOTE_ROOT}/dse_ds/{operator}/{alg}/best_config.json 2>/dev/null"
        )
        best = stdout.read().decode()
        summary[key]["best_config"] = json.loads(best) if best.strip() else None

    out_path = LOCAL_ROOT / "dse_ds" / "board_experiment_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n=== Summary saved ===", out_path)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    ssh.close()


if __name__ == "__main__":
    main()
