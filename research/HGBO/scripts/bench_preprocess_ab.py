"""Benchmark clean0606 letterbox (CPU) vs HGBO VideoPreFuse (NPU) on board."""
from __future__ import annotations

import json
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
HGBO = "/home/HwHiAiUser/HGBO"
BEST_CFG = {
    "split_axis": "flat",
    "tile_h": 4,
    "tile_w": 64,
    "tile_len": 512,
    "blockDim": 1,
    "buffer_num": 1,
    "pipeline_mode": "double_buffer",
    "align_policy": "strict",
}

BENCH_PY = r'''
import json, time, statistics, sys
from pathlib import Path
import cv2
import numpy as np

# --- clean0606 letterbox (from run_board_runtime.py) ---
def letterbox(img, new_shape=(640, 640), color=(114, 114, 114)):
    shape = img.shape[:2]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    ratio = (r, r)
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2
    if shape[::-1] != new_unpad:
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return img, ratio, (dw, dh)

def letterbox_plus_norm(img_bgr):
    """letterbox + BGR2RGB + CHW + float (YOLO-style feed prep on CPU)"""
    img, _, _ = letterbox(img_bgr, (640, 640))
    img = img[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    return np.ascontiguousarray(img)

def bench(fn, warmup=5, repeats=30):
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return {
        "median_ms": statistics.median(samples),
        "mean_ms": statistics.mean(samples),
        "min_ms": min(samples),
        "max_ms": max(samples),
    }

# simulate PC->board JPEG frame decode path: 1280x720 BGR (typical after imdecode)
rng = np.random.default_rng(42)
frame = rng.integers(0, 256, (720, 1280, 3), dtype=np.uint8)

result = {
    "input_shape": [720, 1280, 3],
    "output_shape": [640, 640, 3],
    "platform": "Ascend310B4 board ARM CPU (OpenCV)",
}

result["letterbox_only"] = bench(lambda: letterbox(frame.copy()))
result["letterbox_bgr2rgb_chw_norm"] = bench(lambda: letterbox_plus_norm(frame.copy()))

# emotion-style small crop preprocess (also CPU in clean0606)
roi = frame[100:300, 200:400]
def emotion_prep():
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    r = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
    _ = (r.astype(np.float32) / 255.0)
result["emotion_preprocess_64x64"] = bench(emotion_prep)

print(json.dumps(result, indent=2))
'''

VPF_BENCH = f"""
import json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, '{HGBO}')
cfg = {json.dumps(BEST_CFG)}
cfg_path = Path('/tmp/vpf_best_cfg.json')
cfg_path.write_text(json.dumps(cfg))
import os
os.chdir('{HGBO}/operators/video_pre_fuse')
r = subprocess.run([sys.executable, 'benchmark.py', str(cfg_path)], capture_output=True, text=True, timeout=120)
print(r.stdout[-2000:] if r.stdout else '')
print(r.stderr[-1000:] if r.stderr else '', file=sys.stderr)
br = Path('benchmark_result.json')
if br.exists():
    d = json.loads(br.read_text())
    print('VPF_NPU_RESULT', json.dumps({{k: d.get(k) for k in ['backend','latency_ms','compile_status','correct']}}))
"""

REMOTE = f"""#!/bin/bash
set -e
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize

echo '=== A. clean0606 CPU preprocess (OpenCV letterbox) ==='
python3 /tmp/bench_letterbox.py

echo
echo '=== B. HGBO VideoPreFuse NPU (best DSE config) ==='
source {HGBO}/.venv/bin/activate 2>/dev/null || true
cd {HGBO}
python3 /tmp/bench_vpf_npu.py
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/bench_letterbox.py", "w") as f:
    f.write(BENCH_PY)
with sftp.open("/tmp/bench_vpf_npu.py", "w") as f:
    f.write(VPF_BENCH)
with sftp.open("/tmp/run_ab_compare.sh", "w") as f:
    f.write(REMOTE)
sftp.close()

_, stdout, stderr = ssh.exec_command("bash /tmp/run_ab_compare.sh", timeout=180)
out = stdout.read().decode(errors="replace")
err = stderr.read().decode(errors="replace")
print(out)
if err.strip():
    print("STDERR:", err[-1500:])

# parse and save summary
summary = {}
for line in out.splitlines():
    if line.strip().startswith("{") and "letterbox_only" in line:
        try:
            # multi-line json block - find full json
            pass
        except Exception:
            pass
    if line.startswith("VPF_NPU_RESULT"):
        summary["vpf_npu"] = json.loads(line.split("VPF_NPU_RESULT", 1)[1].strip())

# extract letterbox json block
start = out.find('{\n  "input_shape"')
if start >= 0:
    depth = 0
    for i, ch in enumerate(out[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                summary["clean0606_cpu"] = json.loads(out[start : i + 1])
                break

if summary:
    out_path = __import__("pathlib").Path(__file__).resolve().parents[1] / "dse_ds" / "preprocess_ab_compare.json"
    # compute speedups
    if "clean0606_cpu" in summary and "vpf_npu" in summary:
        lb = summary["clean0606_cpu"]["letterbox_bgr2rgb_chw_norm"]["median_ms"]
        npu = summary["vpf_npu"]["latency_ms"]
        summary["comparison"] = {
            "clean0606_letterbox_norm_median_ms": lb,
            "hgbo_vpf_npu_ms": npu,
            "npu_speedup_vs_letterbox_norm": round(lb / max(npu, 1e-9), 1),
            "note": "算法不完全相同：clean0606=letterbox+padding；HGBO=nearest resize+norm",
        }
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n=== Saved ===", out_path)
    print(json.dumps(summary.get("comparison", summary), indent=2, ensure_ascii=False))

ssh.close()
