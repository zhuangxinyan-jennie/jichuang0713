#requires -Version 5.1
<#
.SYNOPSIS
  One-click full demo: board + Agent + TTS + board_bridge + web

.EXAMPLE
  Double-click: 一键启动完整演示.bat
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\start-full-demo.ps1
#>
param(
    [string]$BoardHost = "192.168.137.100",
    [switch]$SkipTts,
    [switch]$NoBoard,
    [switch]$NoOpenBrowser,
    [switch]$ReuseExisting,
    [string]$AsrBackend = "ctc"
)

$ErrorActionPreference = "Stop"
chcp 65001 | Out-Null
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvLocal = Join-Path $Root "env.local.ps1"
$TtsEnvLocal = Join-Path $Root "cosyvoice_live_release\env.local.ps1"
if (Test-Path -LiteralPath $EnvLocal) { . $EnvLocal }
if (Test-Path -LiteralPath $TtsEnvLocal) { . $TtsEnvLocal }

$BearRoot = Join-Path $Root "bear_agent"
$BundleRoot = Join-Path $Root "pre_on_board_local_start_bundle"
$WebRoot = Join-Path $Root "xiongda_app"
$TtsRoot = if ($env:XIONGDA_TTS_ROOT) { $env:XIONGDA_TTS_ROOT } else { Join-Path $Root "cosyvoice_live_release" }
$LogDir = Join-Path $WebRoot "logs\dev-stack"
$BridgeOut = Join-Path $BundleRoot "pc_received_output"
$BridgeLogDir = Join-Path $BundleRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir, $BridgeOut, $BridgeLogDir | Out-Null

$env:BEAR_AGENT_ROOT = $BearRoot
$env:PRE_BOARD_ROOT = $BundleRoot
if (-not $env:BOARD_SPEAKER_URL) { $env:BOARD_SPEAKER_URL = "http://${BoardHost}:9891/play" }
if (-not $env:XIONGDA_TTS_BACKEND) { $env:XIONGDA_TTS_BACKEND = "dashscope" }
if (-not $env:XIONGDA_TTS_DEVICE) { $env:XIONGDA_TTS_DEVICE = "cloud" }
$env:VITE_XIONGDA_TTS_SERVER_PLAY = "1"
$env:VITE_XIONGDA_TTS_URL = "http://127.0.0.1:9890"
$env:VITE_BEAR_AGENT_URL = "http://127.0.0.1:8765"

$WebEnv = Join-Path $WebRoot ".env.local"
@(
    "# auto-written by start-full-demo.ps1: TTS plays on board CS202 speaker"
    "VITE_XIONGDA_TTS_SERVER_PLAY=1"
    "VITE_XIONGDA_TTS_URL=http://127.0.0.1:9890"
    "VITE_BEAR_AGENT_URL=http://127.0.0.1:8765"
) | Set-Content -LiteralPath $WebEnv -Encoding UTF8

function Get-Py {
    param([string]$Preferred)
    if ($Preferred -and (Test-Path -LiteralPath $Preferred)) { return $Preferred }
    $bearPy = Join-Path $BearRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $bearPy) { return $bearPy }
    if ($env:JICHUANG_PYTHON -and (Test-Path -LiteralPath $env:JICHUANG_PYTHON)) { return $env:JICHUANG_PYTHON }
    return "python"
}

function Test-UrlOk {
    param([string]$Url, [int]$TimeoutSec = 2)
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Wait-Health {
    param([string]$Url, [int]$Max = 60, [System.Diagnostics.Process]$Proc = $null)
    for ($i = 0; $i -lt $Max; $i++) {
        if ($Proc -and $Proc.HasExited) { return $false }
        if (Test-UrlOk $Url) { return $true }
        if (($i + 1) % 6 -eq 0) { Write-Host "." -NoNewline -ForegroundColor DarkGray }
        Start-Sleep -Milliseconds 500
    }
    Write-Host ""
    return $false
}

function Stop-PortListeners {
    param([int[]]$Ports)
    foreach ($port in $Ports) {
        Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
            ForEach-Object {
                Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
            }
    }
}

function Stop-MatchProcesses {
    param([string]$Pattern)
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and ($_.CommandLine -match $Pattern) } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

function Add-FirewallRules {
    foreach ($port in @(18082, 18083, 8770)) {
        $ruleName = "Xiongda board TCP $port"
        netsh advfirewall firewall add rule name=$ruleName dir=in action=allow protocol=TCP localport=$port 2>$null | Out-Null
    }
}

function Ensure-Paramiko {
    param([string]$PythonExe)
    & $PythonExe -c "import paramiko" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[info] installing paramiko ..." -ForegroundColor Yellow
        & $PythonExe -m pip install paramiko
    }
}

$py = Get-Py ""
$pyTts = Get-Py $env:COSYVOICE_PYTHON
$agentPort = if ($env:BEAR_AGENT_PORT) { [int]$env:BEAR_AGENT_PORT } else { 8765 }
$ttsPort = if ($env:XIONGDA_TTS_PORT) { [int]$env:XIONGDA_TTS_PORT } else { 9890 }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Xiongda FULL DEMO one-click start" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ("Board: {0}" -f $BoardHost)
Write-Host "Web:   http://127.0.0.1:5173"
Write-Host ("Agent: http://127.0.0.1:{0}   TTS: http://127.0.0.1:{1}" -f $agentPort, $ttsPort)
Write-Host ("Speaker URL: {0}" -f $env:BOARD_SPEAKER_URL)
Write-Host ""

if (-not (Test-Path -LiteralPath (Join-Path $BearRoot "integration_test\server.py"))) {
    throw "bear_agent missing"
}
if (-not (Test-Path -LiteralPath (Join-Path $WebRoot "package.json"))) {
    throw "xiongda_app missing"
}

Add-FirewallRules
Ensure-Paramiko $py

$procAgent = $null
$procTts = $null
$procBridge = $null
$pushed = $false

try {
    if (-not $ReuseExisting) {
        Write-Host "[0/6] stop old PC processes ..." -ForegroundColor Yellow
        Stop-MatchProcesses 'board_bridge\.run_pipeline|integration_test\\server\.py|integration_test/server\.py|tts_server\.py'
        Stop-PortListeners @(8765, 9890, 5173, 18082, 18083, 8770)
        Start-Sleep -Seconds 2
        Write-Host "      done" -ForegroundColor Green
    }

    Write-Host "[1/6] Bear Agent ..." -ForegroundColor Yellow
    if ((-not $ReuseExisting) -or -not (Test-UrlOk "http://127.0.0.1:$agentPort/health")) {
        $procAgent = Start-Process -FilePath $py `
            -ArgumentList "integration_test\server.py" `
            -WorkingDirectory $BearRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $LogDir "bear_agent.stdout.log") `
            -RedirectStandardError (Join-Path $LogDir "bear_agent.stderr.log") `
            -PassThru
        if (-not (Wait-Health "http://127.0.0.1:$agentPort/health" -Max 80 -Proc $procAgent)) {
            throw "Agent not ready. See $LogDir\bear_agent.stderr.log"
        }
    }
    Write-Host ("      OK  http://127.0.0.1:{0}/health" -f $agentPort) -ForegroundColor Green

    if (-not $SkipTts) {
        Write-Host "[2/6] Cloud TTS -> board CS202 ..." -ForegroundColor Yellow
        if (-not $env:DASHSCOPE_API_KEY) {
            Write-Host "      WARN: DASHSCOPE_API_KEY missing (check cosyvoice_live_release\env.local.ps1)" -ForegroundColor DarkYellow
        }
        if ((-not $ReuseExisting) -or -not (Test-UrlOk "http://127.0.0.1:$ttsPort/health")) {
            $procTts = Start-Process -FilePath $pyTts `
                -ArgumentList "tts_server.py" `
                -WorkingDirectory $TtsRoot `
                -WindowStyle Hidden `
                -RedirectStandardOutput (Join-Path $LogDir "tts_server.stdout.log") `
                -RedirectStandardError (Join-Path $LogDir "tts_server.stderr.log") `
                -PassThru
            if (Wait-Health "http://127.0.0.1:$ttsPort/health" -Max 40 -Proc $procTts) {
                Write-Host ("      OK  http://127.0.0.1:{0}/health" -f $ttsPort) -ForegroundColor Green
            } else {
                Write-Host "      WARN: TTS not ready yet. See tts_server.stderr.log" -ForegroundColor DarkYellow
            }
        } else {
            Write-Host "      OK (already running)" -ForegroundColor Green
        }
    } else {
        Write-Host "[2/6] Skip TTS (-SkipTts)" -ForegroundColor DarkGray
    }

    if (-not $NoBoard) {
        Write-Host "[3/6] Board runtime + CS202 speaker ..." -ForegroundColor Yellow
        $boardScript = Join-Path $Root "scripts\_start_board_full_demo.py"
        if (-not (Test-Path -LiteralPath $boardScript)) { throw "missing $boardScript" }
        & $py $boardScript
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
            throw "board start failed exit=$LASTEXITCODE"
        }
        $spkOk = $false
        for ($i = 0; $i -lt 20; $i++) {
            if (Test-UrlOk "http://${BoardHost}:9891/health") { $spkOk = $true; break }
            Start-Sleep -Milliseconds 500
        }
        if ($spkOk) {
            Write-Host ("      OK  http://{0}:9891/health" -f $BoardHost) -ForegroundColor Green
        } else {
            Write-Host "      WARN: board speaker :9891 not responding" -ForegroundColor DarkYellow
        }
    } else {
        Write-Host "[3/6] Skip board (-NoBoard)" -ForegroundColor DarkGray
    }

    Write-Host "[4/6] board_bridge 18082/18083 ..." -ForegroundColor Yellow
    if ((-not $ReuseExisting) -or -not (Get-NetTCPConnection -LocalPort 18082 -State Listen -ErrorAction SilentlyContinue)) {
        $env:PYTHONPATH = "$BearRoot;$BundleRoot"
        $procBridge = Start-Process -FilePath $py `
            -ArgumentList @(
                "-u", "-m", "board_bridge.run_pipeline",
                "--output-dir", $BridgeOut,
                "--agent-url", "http://127.0.0.1:$agentPort/api/process",
                "--bind-host", "0.0.0.0"
            ) `
            -WorkingDirectory $BearRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $BridgeLogDir "bear_board_bridge.log") `
            -RedirectStandardError (Join-Path $BridgeLogDir "bear_board_bridge.err.log") `
            -PassThru
        Start-Sleep -Seconds 3
        $listen = Get-NetTCPConnection -LocalPort 18082 -State Listen -ErrorAction SilentlyContinue
        if (-not $listen) {
            throw "board_bridge not listening 18082. See $BridgeLogDir\bear_board_bridge.err.log"
        }
    }
    Write-Host "      OK  listening" -ForegroundColor Green

    Write-Host "[5/6] force-idle multimodal gate + checks ..." -ForegroundColor Yellow
    try {
        Invoke-WebRequest -Method Post -Uri "http://127.0.0.1:$agentPort/api/multimodal/force-idle" `
            -UseBasicParsing -TimeoutSec 5 | Out-Null
        Write-Host "      gate idle" -ForegroundColor Green
    } catch {
        Write-Host "      gate skip" -ForegroundColor DarkGray
    }

    $checks = @(
        @{ Name = "Agent"; Url = "http://127.0.0.1:$agentPort/health" },
        @{ Name = "TTS"; Url = "http://127.0.0.1:$ttsPort/health" },
        @{ Name = "BoardSpeaker"; Url = "http://${BoardHost}:9891/health" }
    )
    foreach ($c in $checks) {
        if ($SkipTts -and $c.Name -eq "TTS") { continue }
        if ($NoBoard -and $c.Name -eq "BoardSpeaker") { continue }
        if (Test-UrlOk $c.Url) {
            Write-Host ("      OK {0}" -f $c.Name) -ForegroundColor Green
        } else {
            Write-Host ("      FAIL {0}  {1}" -f $c.Name, $c.Url) -ForegroundColor DarkYellow
        }
    }

    Write-Host "[6/6] Vite web ..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "----------------------------------------" -ForegroundColor Magenta
    Write-Host " Open: http://127.0.0.1:5173" -ForegroundColor Magenta
    Write-Host " Top-left shows person detected / not detected" -ForegroundColor Magenta
    Write-Host " Speak to BOARD camera + mic; audio on CS202" -ForegroundColor Magenta
    Write-Host " Ctrl+C in this window stops PC services" -ForegroundColor DarkGray
    Write-Host " Full stop (incl. board): .\stop-full-demo.ps1" -ForegroundColor DarkGray
    Write-Host "----------------------------------------" -ForegroundColor Magenta
    Write-Host ""

    if (-not $NoOpenBrowser) {
        Start-Process "http://127.0.0.1:5173" | Out-Null
    }

    Push-Location $WebRoot
    $pushed = $true
    if (-not (Test-Path -LiteralPath (Join-Path $WebRoot "node_modules"))) {
        Write-Host "[info] npm install (first time) ..." -ForegroundColor Yellow
        npm install
    }
    npm run dev
}
finally {
    if ($pushed) { Pop-Location -ErrorAction SilentlyContinue }
    Write-Host ""
    Write-Host "[cleanup] stopping PC Agent/TTS/bridge ..." -ForegroundColor DarkGray
    if ($procBridge -and -not $procBridge.HasExited) {
        Stop-Process -Id $procBridge.Id -Force -ErrorAction SilentlyContinue
    }
    if ($procTts -and -not $procTts.HasExited) {
        Stop-Process -Id $procTts.Id -Force -ErrorAction SilentlyContinue
    }
    if ($procAgent -and -not $procAgent.HasExited) {
        Stop-Process -Id $procAgent.Id -Force -ErrorAction SilentlyContinue
    }
    Stop-MatchProcesses 'board_bridge\.run_pipeline|integration_test\\server\.py|integration_test/server\.py'
    Stop-PortListeners @(8765, 18082, 18083, 8770)
    Write-Host "[cleanup] PC stopped. For board too: .\stop-full-demo.ps1" -ForegroundColor DarkGray
}
