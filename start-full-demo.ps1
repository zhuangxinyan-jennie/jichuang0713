#requires -Version 5.1
<#
.SYNOPSIS
  One-click full demo: board inference + Agent/TTS + web + board_bridge

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File F:\jichuang2026\clean_0606\start-full-demo.ps1
#>
param(
    [string]$BoardHost = "192.168.137.100",
    [switch]$SkipTts,
    [switch]$NoBoard,
    [switch]$NoOpenBrowser,
    [string]$AsrBackend = "ctc"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvLocal = Join-Path $Root "env.local.ps1"
if (Test-Path -LiteralPath $EnvLocal) { . $EnvLocal }

$BearRoot = Join-Path $Root "bear_agent"
$BundleRoot = Join-Path $Root "pre_on_board_local_start_bundle"
$WebRoot = Join-Path $Root "xiongda_app"
$RunAll = Join-Path $BundleRoot "run_all.py"
$TtsRoot = if ($env:XIONGDA_TTS_ROOT) { $env:XIONGDA_TTS_ROOT } else { Join-Path $Root "cosyvoice_live_release" }

$env:BEAR_AGENT_ROOT = $BearRoot
$env:PRE_BOARD_ROOT = $BundleRoot

$BearVenvPy = Join-Path $BearRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $BearVenvPy) {
    $env:JICHUANG_PYTHON = $BearVenvPy
}

function Ensure-Paramiko {
    param([string]$PythonExe)
    & $PythonExe -c "import paramiko" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing paramiko for SSH board startup..." -ForegroundColor Yellow
        & $PythonExe -m pip install paramiko
    }
}

function Get-Py {
    param([string]$Preferred)
    if ($Preferred -and (Test-Path -LiteralPath $Preferred)) { return $Preferred }
    if ($env:JICHUANG_PYTHON -and (Test-Path -LiteralPath $env:JICHUANG_PYTHON)) { return $env:JICHUANG_PYTHON }
    return "python"
}

function Wait-Health {
    param(
        [string]$Url,
        [int]$Max = 60,
        [System.Diagnostics.Process]$Proc = $null
    )
    for ($i = 0; $i -lt $Max; $i++) {
        if ($Proc -and $Proc.HasExited) { return $false }
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { return $true }
        } catch {
            if (($i + 1) % 4 -eq 0) { Write-Host "." -NoNewline -ForegroundColor DarkGray }
            Start-Sleep -Milliseconds 500
        }
    }
    Write-Host ""
    return $false
}

function Add-FirewallRules {
    foreach ($port in @(18082, 18083)) {
        $ruleName = "Xiongda board result TCP $port"
        netsh advfirewall firewall add rule name=$ruleName dir=in action=allow protocol=TCP localport=$port 2>$null | Out-Null
    }
}

$py = Get-Py ""
Ensure-Paramiko $py
Write-Host "Python: $py" -ForegroundColor DarkGray
$agentPort = if ($env:BEAR_AGENT_PORT) { [int]$env:BEAR_AGENT_PORT } else { 8765 }
$ttsPort = if ($env:XIONGDA_TTS_PORT) { [int]$env:XIONGDA_TTS_PORT } else { 9890 }
$logDir = Join-Path $WebRoot "logs\dev-stack"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Xiongda full demo" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Board: $BoardHost  ASR: $AsrBackend  (board local camera+mic)"
Write-Host "Agent: http://127.0.0.1:$agentPort  Web: http://localhost:5173"
Write-Host ""

if (-not (Test-Path -LiteralPath $RunAll)) { throw "run_all.py not found: $RunAll" }
if (-not (Test-Path -LiteralPath (Join-Path $BearRoot "integration_test\server.py"))) { throw "bear_agent not found" }

Add-FirewallRules

$procAgent = $null
$procTts = $null
$pushed = $false

try {
    Write-Host "[1/4] Starting Bear Agent..." -ForegroundColor Yellow
    $procAgent = Start-Process -FilePath $py `
        -ArgumentList "integration_test\server.py" `
        -WorkingDirectory $BearRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDir "bear_agent.stdout.log") `
        -RedirectStandardError (Join-Path $logDir "bear_agent.stderr.log") `
        -PassThru
    $agentHealth = "http://127.0.0.1:$agentPort/health"
    if (-not (Wait-Health $agentHealth)) {
        throw "Bear Agent not ready. See $logDir\bear_agent.stderr.log"
    }
    Write-Host "      OK  $agentHealth" -ForegroundColor Green

    if (-not $SkipTts) {
        Write-Host "[2/4] Starting TTS (first boot may be slow)..." -ForegroundColor Yellow
        $pyTts = Get-Py $env:COSYVOICE_PYTHON
        $procTts = Start-Process -FilePath $pyTts `
            -ArgumentList "tts_server.py" `
            -WorkingDirectory $TtsRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $logDir "tts_server.stdout.log") `
            -RedirectStandardError (Join-Path $logDir "tts_server.stderr.log") `
            -PassThru
        $ttsHealth = "http://127.0.0.1:$ttsPort/health"
        Write-Host "      waiting for TTS (max ~15s, first boot can be slow)..." -ForegroundColor DarkGray
        if (Wait-Health $ttsHealth -Max 30 -Proc $procTts) {
            Write-Host "      OK  $ttsHealth" -ForegroundColor Green
        } else {
            if ($procTts.HasExited) {
                Write-Host "      WARN TTS process exited (see $logDir\tts_server.stderr.log). Continuing without speech." -ForegroundColor DarkYellow
            } else {
                Write-Host "      WARN TTS not ready yet; continuing (web may have no voice)" -ForegroundColor DarkYellow
            }
        }
    } else {
        Write-Host "[2/4] Skip TTS (-SkipTts)" -ForegroundColor DarkGray
    }

    Write-Host "[3/4] Board runtime + board_bridge (SSH, ports 18082/18083)..." -ForegroundColor Yellow
    $runAllArgs = @(
        $RunAll,
        "--bear-bridge",
        "--host", $BoardHost,
        "--asr-backend", $AsrBackend,
        "--bear-agent-root", $BearRoot
    )
    if ($NoBoard) { $runAllArgs += "--no-board" }
    & $py @runAllArgs
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "run_all.py failed exit=$LASTEXITCODE" }
    Write-Host "      OK  board + bridge running in background" -ForegroundColor Green
    Write-Host "      log: $BundleRoot\logs\bear_board_bridge.log" -ForegroundColor DarkGray

    Write-Host "[4/4] Starting web (npm run dev)..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "In browser: enable board-auto WebGL sync if shown." -ForegroundColor Magenta
    Write-Host "Talk to the BOARD camera/mic. Ctrl+C stops Agent/TTS in this window." -ForegroundColor DarkGray
    Write-Host ""

    if (-not $NoOpenBrowser) {
        Start-Process "http://localhost:5173" | Out-Null
    }

    Push-Location $WebRoot
    $pushed = $true
    npm run dev
}
finally {
    if ($pushed) { Pop-Location -ErrorAction SilentlyContinue }
    if ($procTts -and -not $procTts.HasExited) {
        Write-Host "[cleanup] stopping TTS..." -ForegroundColor DarkGray
        Stop-Process -Id $procTts.Id -Force -ErrorAction SilentlyContinue
    }
    if ($procAgent -and -not $procAgent.HasExited) {
        Write-Host "[cleanup] stopping Bear Agent..." -ForegroundColor DarkGray
        Stop-Process -Id $procAgent.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[cleanup] done. Board keeps running. Stop local bridge with:" -ForegroundColor DarkGray
    Write-Host "  cd $BundleRoot; python run_all.py --stop" -ForegroundColor DarkGray
}
