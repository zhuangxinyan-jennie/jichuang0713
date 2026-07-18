# -*- coding: utf-8 -*-
"""Download teammate PR binary assets (ONNX/OM) when GitHub is reachable."""
from __future__ import annotations

import base64
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "pre_on_board_local_start_bundle"
PR3_SHA = "d2532d1e5554ddaecc0145137a25b14f4ad3407c"
PR2_SHA = "ee723c8dcb975c444c004a44cb727cc11c007eae"

# (url_or_blob_sha, dest, min_bytes)
FILES: list[tuple[str, Path, int]] = [
    (
        "61e885d9fd4917952d5c1b28b03ccb6a15a35aa2",
        BUNDLE / "motion/artifacts/action_stgcn_upperbody.onnx",
        1_000_000,
    ),
    (
        f"https://media.githubusercontent.com/media/zhuangxinyan-jennie/jichuang0713/{PR3_SHA}/"
        "pre_on_board_local_start_bundle/pre_on_board/models_om/action_stgcn_upperbody.om",
        BUNDLE / "pre_on_board/models_om/action_stgcn_upperbody.om",
        1_000_000,
    ),
    (
        f"https://media.githubusercontent.com/media/zhuangxinyan-jennie/jichuang0713/{PR2_SHA}/"
        "board_handoff_for_teammate/board_stgcn_handoff_20260712_165811/"
        "board_stgcn_handoff_stage/board/models_om/yolo11n_pose_640_aipp_dfl_small_channel_pc.om",
        BUNDLE / "pre_on_board/models_om/yolo11n_pose_640_aipp_dfl_small_channel_pc.om",
        5_000_000,
    ),
]


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def download_url(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "download-teammate-models/1.0"})
    with _opener().open(req, timeout=300) as resp:
        data = resp.read()
    dest.write_bytes(data)
    print(f"OK {dest.relative_to(ROOT)} ({len(data)} bytes)")


def download_blob(sha: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://api.github.com/repos/zhuangxinyan-jennie/jichuang0713/git/blobs/{sha}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "download-teammate-models/1.0",
            "Accept": "application/vnd.github+json",
        },
    )
    with _opener().open(req, timeout=300) as resp:
        payload = json.loads(resp.read())
    data = base64.b64decode(payload["content"])
    dest.write_bytes(data)
    print(f"OK {dest.relative_to(ROOT)} ({len(data)} bytes, blob {sha[:8]})")


def download(source: str, dest: Path) -> None:
    if source.startswith("http://") or source.startswith("https://"):
        download_url(source, dest)
    else:
        download_blob(source, dest)


def main() -> int:
    ok = 0
    for source, dest, min_size in FILES:
        if dest.is_file() and dest.stat().st_size >= min_size:
            print(f"skip {dest.name} (already present)")
            ok += 1
            continue
        for attempt in range(5):
            try:
                download(source, dest)
                ok += 1
                break
            except Exception as exc:  # noqa: BLE001
                wait = 2 ** attempt
                print(f"retry {dest.name}: {exc}; sleep {wait}s")
                time.sleep(wait)
        else:
            print(f"FAIL {dest.name}")
    print(json.dumps({"downloaded": ok, "total": len(FILES)}, ensure_ascii=False))
    return 0 if ok == len(FILES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
