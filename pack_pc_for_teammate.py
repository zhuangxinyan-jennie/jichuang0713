"""Create a teammate handoff archive from clean_0606 (skip locked/cache files)."""
from __future__ import annotations

import argparse
import os
import tarfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT / "board_handoff_for_teammate"

# 队友一般不需要这些（体积大、可重建、或已在板端包里）
EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".venv",
    ".conda_env",
    "node_modules",
    "dist",
    "build",
    ".vite",
    ".cache",
    "cache",
    "board_handoff_for_teammate",
    "pretrained_models",
    "cozy_ref",
    "cosyvoice_live_release",
    "third_party",
    "XiongdaUnityProject",
    "gesture_cursor_project",
}

EXCLUDE_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".zip",
    ".7z",
    ".rar",
    ".mp4",
    ".unitypackage",
}

EXCLUDE_FILE_NAMES = {
    "env.local.ps1",
    ".env",
}


def should_skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    for part in rel.parts:
        if part in EXCLUDE_DIR_NAMES:
            return True
    if path.name in EXCLUDE_FILE_NAMES:
        return True
    if path.suffix.lower() in EXCLUDE_FILE_SUFFIXES:
        return True
    return False


def add_tree(tf: tarfile.TarFile, src_root: Path, arc_prefix: str, skipped: list[str], locked: list[str]) -> int:
    count = 0
    for path in sorted(src_root.rglob("*")):
        if path.is_dir():
            continue
        if should_skip(path, src_root):
            continue
        arcname = f"{arc_prefix}/{path.relative_to(src_root).as_posix()}"
        try:
            tf.add(path, arcname=arcname, recursive=False)
            count += 1
        except PermissionError:
            locked.append(str(path))
        except OSError as exc:
            if getattr(exc, "winerror", None) == 32 or "being used" in str(exc).lower():
                locked.append(str(path))
            else:
                skipped.append(f"{path}: {exc}")
    return count


def write_readme(out_dir: Path, archive: Path, locked: list[str], skipped: list[str], jichuang_added: bool) -> Path:
    readme = out_dir / f"README_pc_handoff_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    readme.write_text(
        f"""# PC 端项目交接包（clean_0606 精简版）

生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
压缩包：`{archive.name}`

## 包含内容

- `clean_0606/` 精简后的 PC 工程（已排除缓存、虚拟环境、Unity、大模型目录）
{"- `jichuang/` 启动脚本（若本机存在）" if jichuang_added else "- `jichuang/`：本机未找到，请单独提供"}

## 请与板端包一起发给队友

板端完整包（已打好）：
`board_handoff_for_teammate/board_full_project_*.tar.gz`

队友训练代码（请单独拷贝）：
`F:\\动作识别优化后\\` 与 `best.pt`

## 本包故意排除的目录

- `pre_on_board_local_start_bundle/cache/`（含被占用的 `model.fp16.onnx`，队友可自己重新下载 ASR 模型）
- `.venv` / `.conda_env` / `node_modules`
- `XiongdaUnityProject` / `cosyvoice_live_release` / `pretrained_models` 等大资源

## 跳过的被占用文件（{len(locked)}）

"""
        + ("\n".join(f"- `{p}`" for p in locked) if locked else "- 无")
        + f"""

## 其他跳过/失败（{len(skipped)}）

"""
        + ("\n".join(f"- {line}" for line in skipped[:20]) if skipped else "- 无")
        + """

## 解压后建议

1. 解压本包 + 板端 `board_full_project_*.tar.gz`
2. PC 安装环境：运行 `setup-env.ps1`
3. 动作识别问题见 `pre_on_board_local_start_bundle/motion/INTEGRATION.md`
""",
        encoding="utf-8",
    )
    return readme


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = out_dir / f"pc_clean_0606_handoff_{stamp}.tar.gz"

    skipped: list[str] = []
    locked: list[str] = []
    jichuang_root = ROOT.parent / "jichuang"

    print(f"[pack] source: {ROOT}")
    print(f"[pack] output: {archive}")
    print("[pack] excluding cache/venv/node_modules/Unity/large models ...")

    with tarfile.open(archive, "w:gz") as tf:
        n = add_tree(tf, ROOT, "clean_0606", skipped, locked)
        print(f"[pack] added {n} files from clean_0606")
        jichuang_added = False
        if jichuang_root.is_dir():
            m = add_tree(tf, jichuang_root, "jichuang", skipped, locked)
            print(f"[pack] added {m} files from {jichuang_root}")
            jichuang_added = m > 0

    readme = write_readme(out_dir, archive, locked, skipped, jichuang_added)
    size_mb = archive.stat().st_size / (1024 * 1024)
    print(f"[OK] archive: {archive} ({size_mb:.1f} MB)")
    print(f"[OK] readme: {readme}")
    if locked:
        print(f"[WARN] {len(locked)} locked file(s) skipped (this is expected for cache models)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
