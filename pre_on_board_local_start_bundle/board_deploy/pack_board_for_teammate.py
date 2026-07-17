"""Pack board ST-GCN handoff bundle and download to local PC."""
from __future__ import annotations

import argparse
import socket
import tarfile
import time
from datetime import datetime
from pathlib import Path

import paramiko

BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
BOARD_JICHUANG = "/home/HwHiAiUser/jichuang"
REMOTE_TAR = "/tmp/board_stgcn_handoff.tar.gz"


def guess_pc_ip(board_host: str) -> str:
    try:
        with socket.create_connection((board_host, 22), timeout=3.0) as sock:
            return str(sock.getsockname()[0])
    except OSError:
        return "192.168.137.1"


def run_ssh(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def build_remote_pack_script() -> str:
    return f"""set -e
STAGE=/tmp/board_stgcn_handoff_stage
rm -rf "$STAGE" {REMOTE_TAR}
mkdir -p "$STAGE/board/motion" "$STAGE/board/models_om" "$STAGE/board/board_deploy" "$STAGE/jichuang/output" "$STAGE/meta"

# ST-GCN 代码与导出物
cp -a {BOARD_PRE}/motion/. "$STAGE/board/motion/"
rm -rf "$STAGE/board/motion/__pycache__" "$STAGE/board/motion"/*/__pycache__ 2>/dev/null || true

# 动作链路相关 OM（不含 ASR/情绪等大文件）
for om in action_stgcn.om action_stgcn_upperbody.om yolo11n_pose_640.om hand_landmark_sparse.om yolo_face_hand_person.om gesture_mlp.om; do
  if [ -f "{BOARD_PRE}/models_om/$om" ]; then
    cp -a "{BOARD_PRE}/models_om/$om" "$STAGE/board/models_om/"
  fi
done

# 板端运行时与启动脚本
cp -a {BOARD_PRE}/board_deploy/run_board_runtime.py "$STAGE/board/board_deploy/"
cp -a {BOARD_JICHUANG}/run_on_board.sh "$STAGE/jichuang/" 2>/dev/null || true
cp -a {BOARD_JICHUANG}/output/. "$STAGE/jichuang/output/" 2>/dev/null || true

# 环境说明
printf '%s\n' \
  'BOARD_PRE=/home/HwHiAiUser/pre_on_board' \
  'BOARD_JICHUANG=/home/HwHiAiUser/jichuang' \
  'ACTION_BACKEND=stgcn' \
  'DETECTOR_BACKEND=hybrid' \
  'ACTION_INFER_STRIDE=6' \
  > "$STAGE/meta/board_paths.txt"

du -sh "$STAGE"/*
cd /tmp
tar -czf board_stgcn_handoff.tar.gz board_stgcn_handoff_stage
ls -lh {REMOTE_TAR}
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Pack board ST-GCN files and download to PC.")
    ap.add_argument("--host", default="192.168.137.100")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="Mind@123")
    ap.add_argument(
        "--output-dir",
        default=r"F:\jichuang2026\clean_0606\board_handoff_for_teammate",
    )
    ap.add_argument(
        "--bundle-root",
        default=r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle",
    )
    ap.add_argument(
        "--teammate-best-pt",
        default=r"F:\动作识别优化后\best.pt",
    )
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_tar = out_dir / f"board_stgcn_handoff_{stamp}.tar.gz"

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

    print("[pack] creating tarball on board ...")
    remote_script = build_remote_pack_script().replace("'", "'\"'\"'")
    code, out, err = run_ssh(client, f"bash -lc '{remote_script}'", timeout=600)
    print(out)
    if err.strip():
        print(err)
    if code != 0:
        client.close()
        raise RuntimeError(f"remote pack failed: {code}")

    print(f"[download] {REMOTE_TAR} -> {local_tar}")
    sftp = client.open_sftp()
    sftp.get(REMOTE_TAR, str(local_tar))
    sftp.close()
    client.close()

    # 解压到同级目录，并补充 PC 侧说明与队友 best.pt
    extract_dir = out_dir / f"board_stgcn_handoff_{stamp}"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(local_tar, "r:gz") as tf:
        tf.extractall(extract_dir)

    bundle = Path(args.bundle_root)
    pc_notes = extract_dir / "pc_side_notes"
    pc_notes.mkdir(exist_ok=True)
    for rel in [
        "motion/INTEGRATION.md",
        "motion/export/export_stgcn_onnx.py",
        "board_deploy/deploy_action_stgcn.py",
    ]:
        src = bundle / rel
        if src.is_file():
            dst = pc_notes / rel.replace("/", "__")
            dst.write_bytes(src.read_bytes())

    teammate_pt = Path(args.teammate_best_pt)
    if teammate_pt.is_file():
        import shutil

        shutil.copy2(teammate_pt, pc_notes / "teammate_best.pt")

    readme = extract_dir / "README_给队友.md"
    readme.write_text(
        f"""# 板端 ST-GCN 交接包

生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
板子 IP：{args.host}
PC IP（打包时）：{guess_pc_ip(args.host)}

## 包里有什么

### `board_stgcn_handoff_stage/board/`
- `motion/`：板端 ST-GCN 推理代码、ONNX、配置
- `models_om/`：动作识别依赖的 NPU 模型（pose / hand / `action_stgcn_upperbody`）
- `board_deploy/run_board_runtime.py`：板端多模态运行时（含 stgcn 后端）

### `board_stgcn_handoff_stage/jichuang/`
- `run_on_board.sh`：板端启动脚本（默认 `ACTION_BACKEND=stgcn`）
- `output/`：最近运行日志（含 action runtime 启动记录）

### `pc_side_notes/`
- `teammate_best.pt`：你们训练用的原始权重（供对比）
- `INTEGRATION.md`、`export_stgcn_onnx.py`、`deploy_action_stgcn.py`：PC 侧集成说明

## 已知问题（请优先看）

1. **训练分布 vs 板端分布不一致**
   - 训练：MediaPipe Holistic（pose_hands）
   - 板端：YOLO Pose OM + Hand Landmark OM（NPU）

2. **`best.pt` 在「手部关键点缺失」时会塌缩成 `bow 100%`**
   - 全零输入 / 板端常见「有身体无手」输入 → 模型固定输出 bow
   - 这是模型质量问题，不是单纯部署 bug

3. **队友应补交训练产物**
   - `train_summary.json`、`history.csv`、`curves.png`
   - 测试集准确率与混淆矩阵

## 建议队友下一步

1. 用本包里的板端代码 + OM，在 PC 上写脚本对 NTU8 视频 **重新抽 NPU 版 landmarks**
2. 用 NPU landmarks **微调** ST-GCN（或重训）
3. 增加 **idle/动作幅度门控**，避免站着就乱报动作
4. 微调后重新导出 ONNX → ATC → 替换 `models_om/action_stgcn.om`

## 文件路径

- 压缩包：`{local_tar}`
- 解压目录：`{extract_dir}`
""",
        encoding="utf-8",
    )

    print(f"[OK] tarball: {local_tar}")
    print(f"[OK] extracted: {extract_dir}")
    print(f"[OK] readme: {readme}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
