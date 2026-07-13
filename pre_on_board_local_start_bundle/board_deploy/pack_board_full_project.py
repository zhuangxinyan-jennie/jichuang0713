"""Pack entire board project (pre_on_board + jichuang) and download to local PC."""
from __future__ import annotations

import argparse
import socket
import tarfile
from datetime import datetime
from pathlib import Path

import paramiko

BOARD_HOME = "/home/HwHiAiUser"
BOARD_PRE = f"{BOARD_HOME}/pre_on_board"
BOARD_JICHUANG = f"{BOARD_HOME}/jichuang"
REMOTE_TAR = "/tmp/board_full_project.tar.gz"


def guess_pc_ip(board_host: str) -> str:
    try:
        with socket.create_connection((board_host, 22), timeout=3.0) as sock:
            return str(sock.getsockname()[0])
    except OSError:
        return "192.168.137.1"


def run_ssh(client: paramiko.SSHClient, cmd: str, timeout: int = 3600) -> tuple[int, str, str]:
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def build_remote_pack_script() -> str:
    return f"""set -e
rm -f {REMOTE_TAR}
cd {BOARD_HOME}
tar -czf {REMOTE_TAR} \\
  --exclude='__pycache__' \\
  --exclude='*.pyc' \\
  --exclude='.git' \\
  pre_on_board jichuang
ls -lh {REMOTE_TAR}
du -sh pre_on_board jichuang
"""


def download_with_progress(sftp: paramiko.SFTPClient, remote: str, local: Path) -> None:
    remote_stat = sftp.stat(remote)
    total = int(remote_stat.st_size or 0)
    transferred = 0
    last_pct = -1

    def _cb(done: int, _chunk: int) -> None:
        nonlocal transferred, last_pct
        transferred = done
        if total > 0:
            pct = int(done * 100 / total)
            if pct >= last_pct + 5 or pct >= 99:
                print(f"[download] {pct}% ({done // (1024 * 1024)} / {total // (1024 * 1024)} MB)", flush=True)
                last_pct = pct

    sftp.get(remote, str(local), callback=_cb)


def main() -> int:
    ap = argparse.ArgumentParser(description="Pack full board project and download to PC.")
    ap.add_argument("--host", default="192.168.137.100")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="Mind@123")
    ap.add_argument(
        "--output-dir",
        default=r"F:\jichuang2026\clean_0606\board_handoff_for_teammate",
    )
    ap.add_argument("--skip-extract", action="store_true", help="Only keep .tar.gz, do not extract.")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_tar = out_dir / f"board_full_project_{stamp}.tar.gz"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connect {args.host}")
    client.connect(
        args.host,
        username=args.user,
        password=args.password,
        timeout=20,
        allow_agent=False,
        look_for_keys=False,
    )

    print("[pack] creating full project tarball on board (pre_on_board + jichuang) ...")
    remote_script = build_remote_pack_script().replace("'", "'\"'\"'")
    code, out, err = run_ssh(client, f"bash -lc '{remote_script}'", timeout=3600)
    print(out)
    if err.strip():
        print(err)
    if code != 0:
        client.close()
        raise RuntimeError(f"remote pack failed: {code}")

    print(f"[download] {REMOTE_TAR} -> {local_tar}")
    sftp = client.open_sftp()
    download_with_progress(sftp, REMOTE_TAR, local_tar)
    sftp.close()
    client.close()

    readme = out_dir / f"README_board_full_project_{stamp}.md"
    readme.write_text(
        f"""# 板端完整项目交接包

生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
板子 IP：{args.host}
PC IP（打包时）：{guess_pc_ip(args.host)}

## 压缩包内容

| 路径（板端） | 说明 |
|-------------|------|
| `pre_on_board/` | 板端完整运行时（约 1.6GB） |
| `jichuang/` | 启动脚本与运行日志 |

### `pre_on_board/` 主要子目录

- `board_deploy/`：视频/音频运行时脚本
- `models_om/`：全部 NPU 模型（手势、表情、动作、YOLO、ASR 等）
- `motion/`：动作识别 ST-GCN 代码与 ONNX/OM
- `gesture_recognition/`：手势识别
- `sound_to_text/`：语音 ASR（含模型缓存）
- `asr_om/`、`asr_onnx/`、`sherpa_ctc_big/`：语音识别相关

### 未打包（非项目本体 / 过大临时目录）

- `pre_on_board_tmp/`（8GB+ 临时目录）
- `pre_on_board_runtime_fixed.tar.gz`（历史压缩包副本）
- `samples/`、`HGBO/` 等昇腾示例

## 本地文件

- 压缩包：`{local_tar}`
- 解压后顶层应为：`pre_on_board/`、`jichuang/`

## 板端还原方式（给队友参考）

```bash
cd /home/HwHiAiUser
# 备份旧目录后
tar -xzf board_full_project_xxx.tar.gz
bash /home/HwHiAiUser/jichuang/run_on_board.sh
```

## 当前已知动作识别问题

- 队友 `best.pt` 在板端 NPU 特征（尤其手部缺失）下易塌缩为 `bow 100%`
- 需用板端 landmarks 重新微调 ST-GCN，详见 `pre_on_board/motion/INTEGRATION.md`
""",
        encoding="utf-8",
    )

    extract_dir = None
    if not args.skip_extract:
        extract_dir = out_dir / f"board_full_project_{stamp}"
        extract_dir.mkdir(parents=True, exist_ok=True)
        print(f"[extract] -> {extract_dir}")
        with tarfile.open(local_tar, "r:gz") as tf:
            tf.extractall(extract_dir, filter="data")

    print(f"[OK] tarball: {local_tar}")
    print(f"[OK] readme: {readme}")
    if extract_dir:
        print(f"[OK] extracted: {extract_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
