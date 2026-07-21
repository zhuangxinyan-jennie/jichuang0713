"""Deploy the phone App Gateway and board runtime glue to an Ascend board."""
from __future__ import annotations

import argparse
import shlex
from pathlib import Path

import paramiko


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "board_deploy"
JICHUANG = ROOT / "jichuang"
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
BOARD_JICHUANG = "/home/HwHiAiUser/jichuang"


def mkdir_p(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    current = ""
    for part in remote_dir.strip("/").split("/"):
        current += "/" + part
        try:
            sftp.stat(current)
        except OSError:
            sftp.mkdir(current)


def upload_tree(sftp: paramiko.SFTPClient, local_root: Path, remote_root: str) -> None:
    for path in sorted(local_root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        remote = remote_root.rstrip("/") + "/" + path.relative_to(local_root).as_posix()
        mkdir_p(sftp, remote.rsplit("/", 1)[0])
        sftp.put(str(path), remote)
        print(f"[upload] {path.relative_to(local_root)}")


def upload_file(sftp: paramiko.SFTPClient, source: Path, destination: str) -> None:
    mkdir_p(sftp, destination.rsplit("/", 1)[0])
    sftp.put(str(source), destination)
    print(f"[upload] {source.name}")


def run(client: paramiko.SSHClient, command: str, timeout: int = 120) -> None:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    output = stdout.read().decode("utf-8", errors="replace")
    error = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if output.strip():
        print(output.rstrip())
    if error.strip():
        print(error.rstrip())
    if code:
        raise RuntimeError(f"remote command failed: {code}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy Xiongda phone App Gateway")
    parser.add_argument("--host", default="192.168.137.100")
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="Mind@123")
    parser.add_argument("--admin-pin", required=True)
    parser.add_argument("--restart-runtime", action="store_true")
    args = parser.parse_args()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username=args.user, password=args.password, timeout=20, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()
    try:
        upload_tree(sftp, DEPLOY / "app_gateway", f"{BOARD_PRE}/board_deploy/app_gateway")
        upload_file(sftp, DEPLOY / "run_board_runtime.py", f"{BOARD_PRE}/board_deploy/run_board_runtime.py")
        upload_file(sftp, JICHUANG / "run_on_board.sh", f"{BOARD_JICHUANG}/run_on_board.sh")
        upload_file(sftp, JICHUANG / "stop_board.sh", f"{BOARD_JICHUANG}/stop_board.sh")
    finally:
        sftp.close()

    quoted_pin = shlex.quote(args.admin_pin)
    quoted_ip = shlex.quote(args.host)
    install = (
        f"chmod +x {BOARD_PRE}/board_deploy/app_gateway/install_service.sh && "
        f"APP_GATEWAY_ADMIN_PIN={quoted_pin} APP_GATEWAY_BOARD_IP={quoted_ip} "
        f"bash {BOARD_PRE}/board_deploy/app_gateway/install_service.sh"
    )
    run(client, "bash -lc " + shlex.quote(install))
    if args.restart_runtime:
        run(client, f"bash {BOARD_JICHUANG}/run_on_board.sh", timeout=150)
    client.close()
    print("[OK] App Gateway deployed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
