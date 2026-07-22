#requires -Version 5.1
<#
.SYNOPSIS
  Stop full demo PC services; optionally stop board processes.

.EXAMPLE
  .\stop-full-demo.ps1
  .\stop-full-demo.ps1 -KeepBoard
#>
param(
    [string]$BoardHost = "192.168.137.100",
    [switch]$KeepBoard
)

$ErrorActionPreference = "Continue"
chcp 65001 | Out-Null
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvLocal = Join-Path $Root "env.local.ps1"
if (Test-Path -LiteralPath $EnvLocal) { . $EnvLocal }

$BearRoot = Join-Path $Root "bear_agent"
$py = if ($env:JICHUANG_PYTHON -and (Test-Path $env:JICHUANG_PYTHON)) {
    $env:JICHUANG_PYTHON
} elseif (Test-Path (Join-Path $BearRoot ".venv\Scripts\python.exe")) {
    (Join-Path $BearRoot ".venv\Scripts\python.exe")
} else { "python" }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Stop Xiongda FULL DEMO" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

function Stop-PortListeners {
    param([int[]]$Ports)
    foreach ($port in $Ports) {
        Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
            ForEach-Object {
                Write-Host ("  close port {0} pid={1}" -f $port, $_.OwningProcess) -ForegroundColor DarkGray
                Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
            }
    }
}

Write-Host "[1/2] stop PC services ..." -ForegroundColor Yellow
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and (
            $_.CommandLine -match 'board_bridge\.run_pipeline|integration_test\\server\.py|integration_test/server\.py|tts_server\.py|vite'
        )
    } |
    ForEach-Object {
        Write-Host ("  kill pid={0}" -f $_.ProcessId) -ForegroundColor DarkGray
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
Stop-PortListeners @(8765, 9890, 5173, 18082, 18083, 8770)
Write-Host "      PC stopped" -ForegroundColor Green

if (-not $KeepBoard) {
    Write-Host ("[2/2] stop board processes ({0}) ..." -f $BoardHost) -ForegroundColor Yellow
    $stopPy = Join-Path $Root "scripts\_stop_board_all.py"
    if (Test-Path -LiteralPath $stopPy) {
        & $py $stopPy
    } else {
        & $py -c ("import json,paramiko;c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy());c.connect('{0}',username='root',password='Mind@123',timeout=15);cmd='bash /home/HwHiAiUser/jichuang/stop_board.sh >/dev/null 2>&1 || true; pkill -f board_speaker_player.py || true; echo BOARD_STOPPED';_,o,e=c.exec_command('bash -lc '+json.dumps(cmd),timeout=40);print((o.read()+e.read()).decode('utf-8','replace'));c.close()").format($BoardHost)
    }
    Write-Host "      board stop requested" -ForegroundColor Green
} else {
    Write-Host "[2/2] keep board (-KeepBoard)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
