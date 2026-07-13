#requires -Version 5.1
param(
    [string]$BoardHost = "192.168.137.100",
    [int]$DurationSec = 60,
    [switch]$SkipBoardRestart
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Bundle = Join-Path $Root "pre_on_board_local_start_bundle"
$Py = Join-Path $Root "bear_agent\.venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Latency benchmark" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Board: $BoardHost  Duration: ${DurationSec}s"
Write-Host ""

& $Py (Join-Path $Bundle "run_all.py") --stop 2>&1 | Out-Null

foreach ($port in @(18082, 18083)) {
    netsh advfirewall firewall add rule name="Xiongda latency TCP $port" dir=in action=allow protocol=TCP localport=$port 2>$null | Out-Null
}

if (-not $SkipBoardRestart) {
    Write-Host "[1/3] Restart board with BOARD_PROFILE=1..." -ForegroundColor Yellow
    $restartPy = Join-Path $Bundle "board_deploy\restart_board_profile.py"
    & $Py $restartPy --host $BoardHost
    Start-Sleep -Seconds 8
} else {
    Write-Host "[1/3] Skip board restart" -ForegroundColor DarkGray
}

Write-Host "[2/3] Run PC latency probe..." -ForegroundColor Yellow
$report = Join-Path $Bundle "logs\latency_report.json"
& $Py (Join-Path $Bundle "board_deploy\probe_full_latency.py") `
    --duration $DurationSec `
    --board-host $BoardHost `
    --with-asr `
    --out $report

Write-Host "[3/3] Done. Report: $report" -ForegroundColor Green
