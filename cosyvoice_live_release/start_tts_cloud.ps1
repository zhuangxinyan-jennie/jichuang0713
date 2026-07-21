#requires -Version 5.1
param(
    [switch]$Background,
    [switch]$StopExisting,
    [int]$Port = 9890,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$ProjectRoot = Split-Path -Parent $Root

if (-not $Python) {
    if ($env:COSYVOICE_PYTHON -and (Test-Path -LiteralPath $env:COSYVOICE_PYTHON)) {
        $Python = $env:COSYVOICE_PYTHON
    } else {
        $defaultPy = Join-Path $ProjectRoot "third_party\CosyVoice\.venv-clean\Scripts\python.exe"
        if (Test-Path -LiteralPath $defaultPy) { $Python = $defaultPy }
        else { $Python = "python" }
    }
}

$LogOut = Join-Path $Root "tts_cloud.out.log"
$LogErr = Join-Path $Root "tts_cloud.err.log"

function Test-PortInUse {
    param([int]$Port)
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        $listener.Stop()
        return $false
    } catch {
        return $true
    }
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python not found: $Python"
}

if (-not $env:DASHSCOPE_API_KEY) {
    throw "Missing DASHSCOPE_API_KEY. Create an API key in Aliyun Bailian, then set it before starting."
}

$voiceCache = Join-Path $Root "outputs\dashscope_xiongda_voice.json"
if (-not $env:DASHSCOPE_VOICE_ID) {
    if (Test-Path -LiteralPath $voiceCache) {
        Write-Host "[info] Using voice_id from $voiceCache" -ForegroundColor Cyan
    } else {
        throw "Missing DASHSCOPE_VOICE_ID and no cache file. Run: python scripts\enroll_xiongda_dashscope.py"
    }
}

if ($StopExisting -and (Test-PortInUse $Port)) {
    Write-Host ("[stop] Stopping process on port {0}..." -f $Port) -ForegroundColor Yellow
    $connections = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

if (Test-PortInUse $Port) {
    Write-Host ("[info] Port {0} already in use." -f $Port) -ForegroundColor Cyan
    try {
        Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/health" -f $Port) -TimeoutSec 3 | ConvertTo-Json -Depth 5
    } catch {
        Write-Host "[warn] /health did not respond." -ForegroundColor Yellow
    }
    return
}

$env:PYTHONPATH = "$Root;$Root\scripts"
$env:XIONGDA_TTS_BACKEND = "dashscope"
$env:XIONGDA_TTS_DEVICE = "cloud"
$env:XIONGDA_TTS_PORT = [string]$Port
if (-not $env:DASHSCOPE_COSYVOICE_MODEL) { $env:DASHSCOPE_COSYVOICE_MODEL = "cosyvoice-v3-flash" }
if (-not $env:BOARD_SPEAKER_URL) { $env:BOARD_SPEAKER_URL = "http://192.168.137.100:9891/play" }

Write-Host "=== Xiongda DashScope CosyVoice TTS ===" -ForegroundColor Cyan
Write-Host ("URL:    http://127.0.0.1:{0}" -f $Port)
Write-Host ("Model:  {0}" -f $env:DASHSCOPE_COSYVOICE_MODEL)
Write-Host ("Board:  {0}" -f $env:BOARD_SPEAKER_URL)
Write-Host ""

if ($Background) {
    $proc = Start-Process -FilePath $Python `
        -ArgumentList "tts_server.py" `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $LogOut `
        -RedirectStandardError $LogErr `
        -PassThru
    Write-Host ("[start] PID={0}" -f $proc.Id) -ForegroundColor Green
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-PortInUse $Port) {
            try {
                Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/health" -f $Port) -TimeoutSec 3 | ConvertTo-Json -Depth 5
            } catch {}
            return
        }
        if ($proc.HasExited) {
            Write-Host "[error] exited early:" -ForegroundColor Red
            Get-Content -LiteralPath $LogErr -Tail 80 -ErrorAction SilentlyContinue
            exit 1
        }
    }
    Write-Host "[warn] still starting; check logs" -ForegroundColor Yellow
    return
}

& $Python "tts_server.py"
