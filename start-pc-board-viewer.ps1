#requires -Version 5.1
<#
.SYNOPSIS
  PC 端实时显示板载摄像头识别结果（OpenCV 窗口）。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File F:\jichuang2026\clean_0606\start-pc-board-viewer.ps1
#>
param(
    [string]$BoardHost = "192.168.137.100",
    [switch]$RestartBoard,
    [string]$AsrBackend = "ctc"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Bundle = Join-Path $Root "pre_on_board_local_start_bundle"
$Py = Join-Path $Root "bear_agent\.venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

& $Py -c "from PIL import Image" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing Pillow for Chinese overlay..." -ForegroundColor Yellow
    & $Py -m pip install Pillow opencv-python -q
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " PC 板端识别实时窗口" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "板子: $BoardHost  监听: TCP 18082"
Write-Host "窗口名: board_result_viewer  (按 q 退出)"
Write-Host ""

# 结束占用 18082 的 board_bridge（与 viewer 冲突）
& $Py (Join-Path $Bundle "run_all.py") --stop | Out-Null

foreach ($port in @(18082, 18083)) {
    netsh advfirewall firewall add rule name="Xiongda board result TCP $port" dir=in action=allow protocol=TCP localport=$port 2>$null | Out-Null
}

if ($RestartBoard) {
    Write-Host "[1/2] 重启板端摄像头服务..." -ForegroundColor Yellow
    & $Py (Join-Path $Bundle "run_all.py") --host $BoardHost --asr-backend $AsrBackend 2>&1 | ForEach-Object { Write-Host $_ }
    Start-Sleep -Seconds 2
    Write-Host "      板端已重启；若下方窗口未弹出，请关闭后台 pc_result_viewer 后仅运行本脚本。" -ForegroundColor DarkGray
} else {
    Write-Host "[1/2] 跳过板端重启（板端需已在 run_board_runtime --capture-local）" -ForegroundColor DarkGray
}

Write-Host "[2/2] 启动 PC 识别窗口..." -ForegroundColor Yellow
Push-Location (Join-Path $Bundle "board_deploy")
try {
    & $Py "pc_result_viewer.py" --host 0.0.0.0 --port 18082
} finally {
    Pop-Location
}
