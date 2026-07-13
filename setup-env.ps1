#requires -Version 5.1
# 首次在 clean_0606 配置环境：venv + npm + .env
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Py = if (Test-Path "D:\python3.9.0_0303\python.exe") { "D:\python3.9.0_0303\python.exe" } else { "python" }

Write-Host "=== clean_0606 环境配置 ===" -ForegroundColor Cyan

$bear = Join-Path $Root "bear_agent"
$venvPy = Join-Path $bear ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    & $Py -m venv (Join-Path $bear ".venv")
}
$legacyVenv = "F:\jichuang2026\bear_agent\.venv"
$hasLegacy = Test-Path (Join-Path $legacyVenv "Scripts\python.exe")
try {
    & $venvPy -m pip install -U pip -q
    & $venvPy -m pip install -r (Join-Path $bear "integration_test\requirements.txt")
    if (Test-Path (Join-Path $bear "requirements_visitor_pc.txt")) {
        & $venvPy -m pip install -r (Join-Path $bear "requirements_visitor_pc.txt")
    }
    & $venvPy -c "import fastapi" 2>$null
    if ($LASTEXITCODE -ne 0) { throw "pip incomplete" }
}
catch {
    if ($hasLegacy) {
        Write-Host "[warn] pip 失败，从旧 bear_agent 复制 .venv ..." -ForegroundColor Yellow
        Remove-Item (Join-Path $bear ".venv") -Recurse -Force -ErrorAction SilentlyContinue
        robocopy $legacyVenv (Join-Path $bear ".venv") /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
        $venvPy = Join-Path $bear ".venv\Scripts\python.exe"
    } else { throw }
}
Write-Host "[ok] bear_agent .venv" -ForegroundColor Green

Push-Location (Join-Path $Root "xiongda_app")
npm install
Pop-Location
Write-Host "[ok] xiongda_app npm" -ForegroundColor Green

$envDev = Join-Path $Root "xiongda_app\.env.development"
if (-not (Test-Path $envDev)) {
    @"
VITE_BEAR_AGENT_URL=http://127.0.0.1:8765
VITE_XIONGDA_TTS_URL=http://127.0.0.1:9890
"@ | Set-Content $envDev -Encoding UTF8
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root "pretrained_models\CosyVoice2-0.5B") | Out-Null
Write-Host ""
Write-Host "完成。下一步: .\启动PC端完整流程.bat  或  .\start-pc-stack.ps1 -SkipTts" -ForegroundColor Cyan
