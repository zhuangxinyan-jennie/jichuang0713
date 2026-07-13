"""Upload fp16 CTC ONNX from PC to board, then run ATC (实时进度输出)."""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import paramiko

from deploy_ctc_npu import (
    BOARD_PRE,
    FP16_DIR,
    HOST,
    OM_OUT,
    PWD,
    USER,
    _board_script,
    _load_atc_input_shape,
    _upload_runtime_files,
)

HERE = Path(__file__).resolve().parent
LOCAL_ONNX = (
    HERE.parent
    / "cache"
    / "ctc_fp16_upload"
    / "sherpa-onnx-streaming-zipformer-ctc-zh-fp16-2025-06-30"
    / "model.fp16.onnx"
)
REMOTE_ONNX = f"{FP16_DIR}/model.fp16.onnx"


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _sftp_mkdir_p(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    parts = remote_dir.strip("/").split("/")
    cur = ""
    for part in parts:
        cur += "/" + part
        try:
            sftp.stat(cur)
        except OSError:
            sftp.mkdir(cur)


def _remote_size(sftp: paramiko.SFTPClient, path: str) -> int | None:
    try:
        return int(sftp.stat(path).st_size)
    except OSError:
        return None


def _upload_with_progress(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    total = local.stat().st_size
    last_pct = -1
    last_report = time.time()

    def callback(done: int, size: int) -> None:
        nonlocal last_pct, last_report
        pct = int(done * 100 / max(1, size))
        now = time.time()
        if pct != last_pct or now - last_report >= 5:
            _log(f"上传 fp16 ONNX: {pct}% ({done // (1024 * 1024)}MB / {size // (1024 * 1024)}MB)")
            last_pct = pct
            last_report = now

    sftp.put(str(local), remote, callback=callback)
    _log("上传 fp16 ONNX: 100% 完成")


def _stream_remote_command(ssh: paramiko.SSHClient, cmd: str, *, label: str, timeout: int = 1800) -> int:
    _log(f"开始 {label}...")
    transport = ssh.get_transport()
    if transport is None:
        raise RuntimeError("SSH transport unavailable")
    channel = transport.open_session()
    channel.settimeout(timeout)
    channel.get_pty()
    channel.exec_command(cmd)

    start = time.time()
    last_heartbeat = start
    buf_out: list[str] = []

    while True:
        now = time.time()
        if channel.recv_ready():
            chunk = channel.recv(4096).decode(errors="replace")
            print(chunk, end="", flush=True)
            buf_out.append(chunk)
            last_heartbeat = now
        if channel.recv_stderr_ready():
            chunk = channel.recv_stderr(4096).decode(errors="replace")
            print(chunk, end="", file=sys.stderr, flush=True)
            last_heartbeat = now
        if channel.exit_status_ready():
            while channel.recv_ready():
                chunk = channel.recv(4096).decode(errors="replace")
                print(chunk, end="", flush=True)
                buf_out.append(chunk)
            while channel.recv_stderr_ready():
                chunk = channel.recv_stderr(4096).decode(errors="replace")
                print(chunk, end="", file=sys.stderr, flush=True)
            break
        if now - start > timeout:
            _log(f"{label} 超时 ({timeout}s)")
            channel.close()
            return 124
        if now - last_heartbeat >= 30:
            elapsed = int(now - start)
            _log(f"{label} 仍在运行... 已耗时 {elapsed}s（未卡死，ATC 编译较慢属正常）")
            last_heartbeat = now
        time.sleep(0.15)

    code = int(channel.recv_exit_status())
    elapsed = int(time.time() - start)
    _log(f"{label} 结束，exit={code}，耗时 {elapsed}s")
    return code


def main() -> int:
    if not LOCAL_ONNX.is_file():
        _log(f"缺少本地 fp16: {LOCAL_ONNX}")
        return 2

    local_size = LOCAL_ONNX.stat().st_size
    _log(f"本地 fp16 ONNX: {local_size / (1024 * 1024):.1f} MB")

    atc_shape = _load_atc_input_shape()
    _log(f"ATC 输入张量数: {atc_shape.count(';') + 1}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    _log(f"连接板子 {HOST} ...")
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()

    _log("上传运行时 Python 文件...")
    _upload_runtime_files(sftp)
    _sftp_mkdir_p(sftp, FP16_DIR)

    remote_size = _remote_size(sftp, REMOTE_ONNX)
    if remote_size == local_size:
        _log(f"板端已有完整 fp16 ONNX（{remote_size // (1024*1024)}MB），跳过上传")
    else:
        if remote_size:
            _log(f"板端 fp16 大小不一致（{remote_size} vs {local_size}），重新上传")
        else:
            _log("板端无 fp16 ONNX，开始上传（约 5–15 分钟）...")
        _upload_with_progress(sftp, LOCAL_ONNX, REMOTE_ONNX)

    script = _board_script(atc_shape)
    with sftp.open("/tmp/deploy_ctc_npu_atc_only.sh", "w") as fp:
        fp.write(script)
    sftp.close()

    if _remote_size(ssh.open_sftp(), OM_OUT):
        _log(f"检测到已有 OM，将重新 ATC 覆盖: {OM_OUT}")

    code = _stream_remote_command(
        ssh,
        "/bin/bash /tmp/deploy_ctc_npu_atc_only.sh",
        label="板端 ATC 编译",
        timeout=2400,
    )
    ssh.close()

    if code == 0:
        _log("部署成功，接下来可 probe_ctc_om_ready.py 并 ASR_BACKEND=ctc_om 启动")
    else:
        _log(f"部署失败 exit={code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
