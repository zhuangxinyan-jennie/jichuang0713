#requires -Version 5.1
# UTF-8 BOM above: PowerShell 5.x reads this file as UTF-8 on Windows.
<#
.SYNOPSIS
  Start Bear Agent + CosyVoice TTS in background, then npm run dev in foreground (one terminal).

.DESCRIPTION
  Default layout (sibling folders under same parent):
    bear_agent             -> integration_test/server.py  (8765)
    cosyvoice_live_release -> tts_server.py             (9890)
    xiongda_app            -> npm run dev               (Vite port in console)

  Env overrides: BEAR_AGENT_ROOT, XIONGDA_TTS_ROOT, BEAR_AGENT_PORT, XIONGDA_TTS_PORT

  Ctrl+C in this window stops Vite and kills started Agent/TTS child processes.

  -LatencyLog：设置 BEAR_LATENCY_LOG=1，并把 Agent/TTS/board_bridge 共用的延时行写入
    logs/dev-stack/latency_live.log（另启动新窗口实时滚动显示；加 -NoLatencyTailWindow 可关）。
    Agent/TTS 子进程 stdout 仍重定向到 *.stdout.log，延时行主要靠 latency_live.log 与 tail 窗口。
  -NoLatencyTailWindow：与 -LatencyLog 同用时，不自动弹出 tail 窗口（自行 Get-Content -Wait）。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\start-dev-stack.ps1
.EXAMPLE
  .\scripts\start-dev-stack.ps1 -SkipTts
.EXAMPLE
  .\scripts\start-dev-stack.ps1 -LatencyLog
.EXAMPLE
  .\scripts\start-dev-stack.ps1 -LatencyLog -NoLatencyTailWindow
#>
param(
    [switch]$SkipTts,
    [switch]$InstallNpm,
    [switch]$LatencyLog,
    [switch]$NoLatencyTailWindow,
    [switch]$NoResetAgent,
    [switch]$NoOpenBrowser,
    [string]$BearAgentRoot = "",
    [string]$TtsRoot = "",
    [string]$WebRoot = ""
)

$ErrorActionPreference = "Stop"

function Resolve-RepoParent {
    param([string]$ScriptDir)
    return (Resolve-Path (Join-Path $ScriptDir "..")).Path
}

function Pick-Python {
    param([string]$RepoRoot, [switch]$ForTts)
    if ($ForTts) {
        if ($env:COSYVOICE_PYTHON -and (Test-Path -LiteralPath $env:COSYVOICE_PYTHON)) { return $env:COSYVOICE_PYTHON }
        $parent = Split-Path -Parent $RepoRoot
        $cosyPy = Join-Path $parent "third_party\CosyVoice\.venv-clean\Scripts\python.exe"
        if (Test-Path -LiteralPath $cosyPy) { return $cosyPy }
    }
    if ($env:JICHUANG_PYTHON -and (Test-Path -LiteralPath $env:JICHUANG_PYTHON)) { return $env:JICHUANG_PYTHON }
    $projectPy = "C:\Users\tanza\anaconda3\envs\jichuang0505\python.exe"
    if (Test-Path -LiteralPath $projectPy) { return $projectPy }
    return "python"
}

function Set-GpuTtsEnv {
    param([string]$TtsRoot, [string]$PythonExe, [int]$Port)
    if (-not $env:XIONGDA_TTS_DEVICE) { $env:XIONGDA_TTS_DEVICE = "cuda" }
    $env:XIONGDA_TTS_PORT = [string]$Port
    $isCosyVoice = Test-Path -LiteralPath (Join-Path $TtsRoot "cosyvoice_live_release.marker")
    if (-not $isCosyVoice) {
        $isCosyVoice = Test-Path -LiteralPath (Join-Path $TtsRoot "scripts\cosyvoice_repl.py")
    }
    if ($isCosyVoice) {
        $projectRoot = Split-Path -Parent $TtsRoot
        $env:PYTHONPATH = "$TtsRoot;$TtsRoot\scripts"
        if (-not $env:COSYVOICE_MODEL_DIR) { $env:COSYVOICE_MODEL_DIR = Join-Path $projectRoot "pretrained_models\CosyVoice2-0.5B" }
        if (-not $env:COSYVOICE_REPO) { $env:COSYVOICE_REPO = Join-Path $projectRoot "third_party\CosyVoice" }
        if (-not $env:COSYVOICE_STREAM_TOKEN_HOP_LEN) { $env:COSYVOICE_STREAM_TOKEN_HOP_LEN = "20" }
    }
    else {
        if (-not $env:XIONGDA_TTS_FP32) { $env:XIONGDA_TTS_FP32 = "1" }
        $env:PYTHONPATH = "$TtsRoot;$TtsRoot\GPT_SoVITS"
    }

    if ($PythonExe -and $PythonExe -ne "python" -and (Test-Path -LiteralPath $PythonExe)) {
        $envRoot = Split-Path -Parent $PythonExe
        $env:PATH = "$envRoot\bin;$envRoot\Library\bin;$envRoot\Scripts;$envRoot\DLLs;$envRoot\Lib\site-packages\torch\lib;" + $env:PATH
    }
}

function Wait-HealthUrl {
    param([string]$Url, [int]$MaxAttempts = 40)
    for ($i = 0; $i -lt $MaxAttempts; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 1
            if ($r.StatusCode -eq 200) { return $true }
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }
    return $false
}

function Port-InUse {
    param([int]$Port)
    try {
        $l = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
        $l.Start()
        $l.Stop()
        return $false
    }
    catch {
        return $true
    }
}

$scriptsDir = $PSScriptRoot
$webResolved = if ($WebRoot) { (Resolve-Path $WebRoot).Path } else { Resolve-RepoParent $scriptsDir }
$parent = Split-Path -Parent $webResolved

if (-not $BearAgentRoot) { $BearAgentRoot = $(if ($env:BEAR_AGENT_ROOT) { $env:BEAR_AGENT_ROOT } else { Join-Path $parent "bear_agent" }) }
if (-not $TtsRoot) {
    $TtsRoot = if ($env:XIONGDA_TTS_ROOT) {
        $env:XIONGDA_TTS_ROOT
    }
    else { Join-Path $parent "cosyvoice_live_release" }
}

$BearAgentRoot = (Resolve-Path -LiteralPath $BearAgentRoot).Path
if (-not $SkipTts) {
    $TtsRoot = (Resolve-Path -LiteralPath $TtsRoot).Path
}

$agentPy = Join-Path $BearAgentRoot "integration_test\server.py"
$ttsPy = Join-Path $TtsRoot "tts_server.py"
if (-not (Test-Path -LiteralPath $agentPy)) {
    throw ('Bear Agent not found: {0} (set BEAR_AGENT_ROOT).' -f $agentPy)
}
if (-not $SkipTts -and -not (Test-Path -LiteralPath $ttsPy)) {
    throw ('TTS not found: {0} (set XIONGDA_TTS_ROOT or use -SkipTts).' -f $ttsPy)
}

$pyBear = Pick-Python $BearAgentRoot
$pyTts = if (-not $SkipTts) { Pick-Python $TtsRoot -ForTts } else { "" }

$agentPort = if ($env:BEAR_AGENT_PORT) { [int]$env:BEAR_AGENT_PORT } else { 8765 }
$ttsPort = if ($env:XIONGDA_TTS_PORT) { [int]$env:XIONGDA_TTS_PORT } else { 9888 }

$logDir = Join-Path $webResolved "logs\dev-stack"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logAgent = Join-Path $logDir "bear_agent.stdout.log"
$logAgentErr = Join-Path $logDir "bear_agent.stderr.log"
$logTts = Join-Path $logDir "tts_server.stdout.log"
$logTtsErr = Join-Path $logDir "tts_server.stderr.log"

Write-Host '=== xiongda dev stack ===' -ForegroundColor Cyan
Write-Host ('Web:    {0}' -f $webResolved)
Write-Host ('Agent:  {0} (port {1})' -f $BearAgentRoot, $agentPort)
if (-not $SkipTts) { Write-Host ('TTS:    {0} (port {1})' -f $TtsRoot, $ttsPort) }
Write-Host ('Logs:   {0}' -f $logDir)
if ($LatencyLog) {
    $env:BEAR_LATENCY_LOG = '1'
    $latencyLiveLog = Join-Path $logDir 'latency_live.log'
    $null = New-Item -ItemType File -Path $latencyLiveLog -Force
    $env:BEAR_LATENCY_LOG_FILE = $latencyLiveLog
    Write-Host "[latency] BEAR_LATENCY_LOG=1；Agent 推理 + TTS 合成延时写入: $latencyLiveLog" -ForegroundColor Magenta
    if (-not $NoLatencyTailWindow) {
        $tailCmd = "Get-Content -LiteralPath '$latencyLiveLog' -Wait -Encoding UTF8"
        Start-Process -FilePath powershell.exe -ArgumentList @('-NoProfile', '-NoExit', '-Command', $tailCmd) -WorkingDirectory $webResolved | Out-Null
        Write-Host '[latency] 已打开新 PowerShell 窗口实时显示延时（可关掉该窗口，不影响服务）' -ForegroundColor Green
    }
}
Write-Host ""

$procAgent = $null
$procTts = $null
$pushedWeb = $false

try {
    if ($InstallNpm -or -not (Test-Path (Join-Path $webResolved "node_modules"))) {
        if (-not (Test-Path (Join-Path $webResolved "node_modules"))) {
            Write-Host '[npm] node_modules missing; running npm install...' -ForegroundColor Yellow
        }
        Push-Location $webResolved
        npm install
        Pop-Location
    }

    if (Port-InUse $agentPort) {
        Write-Host ('[WARN] Port {0} is already in use; skipping Bear Agent (assume it is running).' -f $agentPort) -ForegroundColor Yellow
    }
    else {
        Write-Host '[start] Bear Agent...'
        $swAgent = [System.Diagnostics.Stopwatch]::StartNew()
        $procAgent = Start-Process -FilePath $pyBear `
            -ArgumentList "integration_test\server.py" `
            -WorkingDirectory $BearAgentRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput $logAgent `
            -RedirectStandardError $logAgentErr `
            -PassThru
        $health = 'http://127.0.0.1:{0}/health' -f $agentPort
        if (-not (Wait-HealthUrl $health)) {
            Write-Host ('[ERROR] Bear Agent did not respond at {0}; see {1}' -f $health, $logAgentErr) -ForegroundColor Red
            throw 'Bear Agent failed to start.'
        }
        $swAgent.Stop()
        Write-Host ('[latency] Bear Agent 首次 /health 就绪: {0}ms' -f $swAgent.ElapsedMilliseconds) -ForegroundColor Magenta
        Write-Host ('[ok] Bear Agent {0}' -f $health) -ForegroundColor Green
    }

    if (-not $SkipTts) {
        if (Port-InUse $ttsPort) {
            Write-Host ('[WARN] Port {0} is already in use; skipping TTS (assume it is running).' -f $ttsPort) -ForegroundColor Yellow
        }
        else {
            Write-Host '[start] TTS...'
            $swTts = [System.Diagnostics.Stopwatch]::StartNew()
            Set-GpuTtsEnv -TtsRoot $TtsRoot -PythonExe $pyTts -Port $ttsPort
            $procTts = Start-Process -FilePath $pyTts `
                -ArgumentList "tts_server.py" `
                -WorkingDirectory $TtsRoot `
                -WindowStyle Hidden `
                -RedirectStandardOutput $logTts `
                -RedirectStandardError $logTtsErr `
                -PassThru
            $ttsHealth = 'http://127.0.0.1:{0}/health' -f $ttsPort
            # GPT-SoVITS 首启常远超 Bear Agent，单独加长探测次数（约可达数十秒，取决于本机）
            if (-not (Wait-HealthUrl $ttsHealth -MaxAttempts 160)) {
                $swTts.Stop()
                Write-Host ('[latency] TTS /health 在加长探测窗口内仍未就绪: {0}ms（若 stderr 仍在 Loading weights，多为正常现象，稍后 curl /health 再试）' -f $swTts.ElapsedMilliseconds) -ForegroundColor Magenta
                Write-Host ('[WARN] TTS did not respond at {0} yet (first boot may be slow). Logs: {1}' -f $ttsHealth, $logTtsErr) -ForegroundColor Yellow
            }
            else {
                $swTts.Stop()
                Write-Host ('[latency] TTS 首次 /health 就绪: {0}ms' -f $swTts.ElapsedMilliseconds) -ForegroundColor Magenta
                Write-Host ('[ok] TTS {0}' -f $ttsHealth) -ForegroundColor Green
            }
        }
    }

    if (-not $NoResetAgent) {
        $resetUrl = 'http://127.0.0.1:{0}/api/reset' -f $agentPort
        try {
            Invoke-WebRequest -Uri $resetUrl -Method Post -UseBasicParsing -TimeoutSec 5 | Out-Null
            Write-Host ('[ok] Bear Agent reset: {0}' -f $resetUrl) -ForegroundColor Green
        }
        catch {
            Write-Host ('[WARN] Bear Agent reset failed: {0}' -f $_.Exception.Message) -ForegroundColor Yellow
        }
    }

    if (-not $NoOpenBrowser) {
        Start-Process 'http://localhost:5173' | Out-Null
    }

    Write-Host ""
    Write-Host '[foreground] npm run dev (Ctrl+C stops Agent/TTS started here)...' -ForegroundColor Cyan
    Push-Location $webResolved
    $pushedWeb = $true
    npm run dev
}
finally {
    if ($pushedWeb) {
        Pop-Location -ErrorAction SilentlyContinue
    }
    if ($procTts -and -not $procTts.HasExited) {
        Write-Host ""
        Write-Host ('[cleanup] Stopping TTS PID {0}...' -f $procTts.Id) -ForegroundColor DarkGray
        Stop-Process -Id $procTts.Id -Force -ErrorAction SilentlyContinue
    }
    if ($procAgent -and -not $procAgent.HasExited) {
        Write-Host ('[cleanup] Stopping Bear Agent PID {0}...' -f $procAgent.Id) -ForegroundColor DarkGray
        Stop-Process -Id $procAgent.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host '[cleanup] Done.' -ForegroundColor DarkGray
}
