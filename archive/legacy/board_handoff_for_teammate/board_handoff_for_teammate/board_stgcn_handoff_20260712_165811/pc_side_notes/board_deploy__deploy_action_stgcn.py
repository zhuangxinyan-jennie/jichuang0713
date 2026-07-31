"""Deploy HolisticLite ST-GCN action model to Ascend board (ONNX -> OM + runtime)."""
from __future__ import annotations

import argparse
import socket
import stat
from pathlib import Path

import paramiko

BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
BOARD_JICHUANG = "/home/HwHiAiUser/jichuang"
SOC_VERSION = "Ascend310B1"
INPUT_SHAPE = "features:1,10,48,75"


def guess_pc_ip(board_host: str) -> str:
    try:
        with socket.create_connection((board_host, 22), timeout=3.0) as sock:
            return str(sock.getsockname()[0])
    except OSError:
        return "192.168.137.1"


def sftp_mkdir_p(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    parts = remote_dir.strip("/").split("/")
    cur = ""
    for part in parts:
        cur += "/" + part
        try:
            sftp.stat(cur)
        except OSError:
            sftp.mkdir(cur)


def upload_tree(sftp: paramiko.SFTPClient, local_root: Path, remote_root: str) -> None:
    skip_dirs = {"__pycache__", ".git", "artifacts"}
    skip_suffixes = {".pyc", ".png", ".csv", ".pt", ".onnx", ".om"}
    for path in sorted(local_root.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(local_root).as_posix()
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix.lower() in skip_suffixes:
            continue
        remote = f"{remote_root}/{rel}".replace("//", "/")
        sftp_mkdir_p(sftp, "/".join(remote.split("/")[:-1]))
        sftp.put(str(path), remote)
        print(f"[upload] {rel}")


def run_ssh(client: paramiko.SSHClient, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def main() -> int:
    ap = argparse.ArgumentParser(description="Deploy action_stgcn.om and ST-GCN runtime to board.")
    ap.add_argument("--host", default="192.168.137.100")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="Mind@123")
    ap.add_argument(
        "--bundle-root",
        default=r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle",
    )
    ap.add_argument(
        "--jichuang-root",
        default=r"F:\jichuang2026\jichuang",
    )
    ap.add_argument(
        "--onnx",
        default=r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\motion\artifacts\action_stgcn.onnx",
    )
    ap.add_argument("--skip-atc", action="store_true", help="Skip ATC if action_stgcn.om already on board.")
    ap.add_argument("--skip-restart", action="store_true")
    args = ap.parse_args()

    bundle = Path(args.bundle_root)
    jichuang = Path(args.jichuang_root)
    onnx_path = Path(args.onnx)
    if not onnx_path.is_file():
        raise FileNotFoundError(f"ONNX not found: {onnx_path}")

    pc_ip = guess_pc_ip(args.host)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        args.host,
        username=args.user,
        password=args.password,
        timeout=15,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = client.open_sftp()

    remote_onnx = f"{BOARD_PRE}/motion/artifacts/action_stgcn.onnx"
    remote_om = f"{BOARD_PRE}/models_om/action_stgcn.om"
    sftp_mkdir_p(sftp, f"{BOARD_PRE}/motion/artifacts")
    sftp.put(str(onnx_path), remote_onnx)
    print(f"[upload] action_stgcn.onnx -> {remote_onnx}")

    if not args.skip_atc:
        atc_cmd = (
            "sh -lc '"
            "source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || "
            "source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh; "
            f"cd {BOARD_PRE}/motion/artifacts && "
            "rm -f action_stgcn.om action_stgcn_linux_aarch64.om 2>/dev/null; "
            f"atc --model=action_stgcn.onnx --framework=5 --output=action_stgcn "
            f"--input_format=ND --input_shape=\"{INPUT_SHAPE}\" "
            f"--soc_version={SOC_VERSION} --log=error && "
            "OM=$(ls -1 action_stgcn*.om | head -1) && "
            f"cp -f \"$OM\" {remote_om} && ls -la \"$OM\" {remote_om}"
            "'"
        )
        code, out, err = run_ssh(client, atc_cmd, timeout=600)
        print(out)
        if err.strip():
            print(err)
        if code != 0:
            client.close()
            raise RuntimeError(f"ATC failed with code {code}")
    else:
        print("[skip] ATC")

    upload_tree(sftp, bundle / "motion", f"{BOARD_PRE}/motion")
    sftp.put(
        str(bundle / "board_deploy" / "run_board_runtime.py"),
        f"{BOARD_PRE}/board_deploy/run_board_runtime.py",
    )
    print("[upload] board_deploy/run_board_runtime.py")

    run_on_board = jichuang / "run_on_board.sh"
    if run_on_board.is_file():
        sftp.put(str(run_on_board), f"{BOARD_JICHUANG}/run_on_board.sh")
        client.exec_command(f"chmod +x {BOARD_JICHUANG}/run_on_board.sh")
        print("[upload] jichuang/run_on_board.sh")

    sftp.close()

    if not args.skip_restart:
        remote_cmd = (
            f"sh -lc 'export ACTION_BACKEND=stgcn DETECTOR_BACKEND=hybrid "
            f"ACTION_INFER_STRIDE=6 BOARD_LOCAL_MIC=1 BOARD_LOCAL_CAMERA=1 "
            f"BOARD_RESULT_HOST={pc_ip} AUDIO_DEVICE=0 VIDEO_DEVICE=0; "
            f"bash {BOARD_JICHUANG}/run_on_board.sh'"
        )
        code, out, err = run_ssh(client, remote_cmd, timeout=120)
        print(out)
        if err.strip():
            print(err)
        if code != 0:
            client.close()
            return code

        code, out, err = run_ssh(
            client,
            f"sh -lc 'sleep 3; grep -E \"action runtime|stgcn|disabled\" {BOARD_JICHUANG}/output/board_video_runtime.log | tail -5'",
            timeout=30,
        )
        print("[verify]", out.strip() or err.strip())

    client.close()
    print("[OK] action_stgcn deployed. ACTION_BACKEND=stgcn DETECTOR_BACKEND=hybrid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
