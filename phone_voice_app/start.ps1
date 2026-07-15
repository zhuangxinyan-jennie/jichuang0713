# Phone Voice 一键启动
param(
  [string]$BoardHost = $env:PHONE_VOICE_BOARD_HOST
)
if (-not $BoardHost) { $BoardHost = "192.168.137.100" }

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\server

python -c "import aiohttp,numpy" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "安装依赖..."
  python -m pip install -r requirements.txt
}

Write-Host "板子 IP: $BoardHost"
python bridge.py --board-host $BoardHost @args
