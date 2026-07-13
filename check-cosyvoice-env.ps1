#requires -Version 5.1
# Windows port of cosyvoice_live_release/check_env.sh — runs in clean_0606 only
$ErrorActionPreference = "Stop"
chcp 65001 | Out-Null

$Root = $PSScriptRoot
$TtsRoot = Join-Path $Root "cosyvoice_live_release"
$CosyRepo = if ($env:COSYVOICE_REPO) { $env:COSYVOICE_REPO } else { Join-Path $Root "third_party\CosyVoice" }
$ModelDir = if ($env:COSYVOICE_MODEL_DIR) { $env:COSYVOICE_MODEL_DIR } else { Join-Path $Root "pretrained_models\CosyVoice2-0.5B" }
$Python = if ($env:COSYVOICE_PYTHON) { $env:COSYVOICE_PYTHON } else { Join-Path $CosyRepo ".venv-clean\Scripts\python.exe" }

Write-Host "release dir: $TtsRoot"
Write-Host "python:      $Python"
Write-Host "cosyvoice:   $CosyRepo"
Write-Host "model:       $ModelDir"

if (-not (Test-Path -LiteralPath $CosyRepo)) { throw "FAIL: CosyVoice source not found" }
if (-not (Test-Path -LiteralPath $ModelDir)) { throw "FAIL: CosyVoice2 model not found" }
if (-not (Test-Path -LiteralPath $Python)) { throw "FAIL: Python not found. Run .\setup-cosyvoice-venv.ps1 first" }

$pyScript = @"
import sys
from pathlib import Path

cosyvoice_repo = Path(r'$CosyRepo')
model_dir = Path(r'$ModelDir')
sys.path.insert(0, str(cosyvoice_repo))
matcha = cosyvoice_repo / 'third_party' / 'Matcha-TTS'
if matcha.exists():
    sys.path.insert(0, str(matcha))

required = [
    'cosyvoice2.yaml', 'llm.pt', 'flow.pt', 'hift.pt',
    'campplus.onnx', 'speech_tokenizer_v2.onnx',
]
missing = [n for n in required if not (model_dir / n).exists()]
if missing:
    raise SystemExit(f'FAIL: missing model files: {missing}')

import torch
import soundfile
import cosyvoice

print('torch:', torch.__version__)
print('cuda_available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('gpu:', torch.cuda.get_device_name(0))
print('soundfile:', soundfile.__version__)
print('cosyvoice:', Path(cosyvoice.__file__).resolve())
try:
    import vllm
    print('vllm:', vllm.__version__)
except Exception as exc:
    print('vllm: unavailable', exc)
"@

& $Python -c $pyScript
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "OK" -ForegroundColor Green
