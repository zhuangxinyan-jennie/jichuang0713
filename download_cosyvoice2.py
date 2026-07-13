"""Download CosyVoice2-0.5B from ModelScope with tqdm progress."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "pretrained_models" / "CosyVoice2-0.5B"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

print("Target:", MODEL_DIR, flush=True)
print("Downloading iic/CosyVoice2-0.5B from ModelScope (progress below)...", flush=True)

from modelscope import snapshot_download

snapshot_download(
    "iic/CosyVoice2-0.5B",
    local_dir=str(MODEL_DIR),
    revision="master",
)

required = ["cosyvoice2.yaml", "llm.pt", "flow.pt", "hift.pt"]
missing = [name for name in required if not (MODEL_DIR / name).exists()]
if missing:
    print("WARN: missing files:", missing, file=sys.stderr)
    sys.exit(2)

print("OK: core model files present.", flush=True)
