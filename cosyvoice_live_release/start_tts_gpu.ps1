#requires -Version 5.1
param(
    [switch]$Background,
    [switch]$StopExisting,
    [int]$Port = 9888,
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
        else { $Python = "C:\Users\tanza\anaconda3\envs\jichuang0505\python.exe" }
    }
}

$EnvRoot = Split-Path -Parent $Python
$LogOut = Join-Path $Root "tts_server.out.log"
$LogErr = Join-Path $Root "tts_server.err.log"

function Test-PortInUse {
    param([int]$Port)
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        $listener.Stop()
        return $false
    }
    catch {
        return $true
    }
}

function Show-Health {
    param([int]$Port)
    try {
        $health = Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/health" -f $Port) -TimeoutSec 3
        Write-Host "[ok] CosyVoice TTS is running:" -ForegroundColor Green
        $health | ConvertTo-Json -Depth 5
    }
    catch {
        Write-Host ("[warn] Port {0} is in use, but /health did not respond." -f $Port) -ForegroundColor Yellow
    }
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python not found: $Python"
}

if ($StopExisting -and (Test-PortInUse $Port)) {
    Write-Host ("[stop] Trying to stop process on port {0}..." -f $Port) -ForegroundColor Yellow
    $connections = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

if (Test-PortInUse $Port) {
    Write-Host ("[info] Port {0} is already in use. Reusing existing TTS service." -f $Port) -ForegroundColor Cyan
    Show-Health -Port $Port
    return
}

$ExtraDllDirs = @(
    (Join-Path $EnvRoot "bin"),
    (Join-Path $EnvRoot "Library\bin"),
    (Join-Path $EnvRoot "Scripts"),
    (Join-Path $EnvRoot "DLLs"),
    (Join-Path $EnvRoot "Lib\site-packages\torch\lib")
) | Where-Object { Test-Path -LiteralPath $_ }

$env:PATH = (($ExtraDllDirs + @($env:PATH)) -join [System.IO.Path]::PathSeparator)
$env:PYTHONPATH = "$Root;$Root\scripts"
$env:XIONGDA_TTS_DEVICE = "cuda"
$env:XIONGDA_TTS_PORT = [string]$Port
$env:COSYVOICE_MODEL_DIR = (Join-Path (Split-Path -Parent $Root) "pretrained_models\CosyVoice2-0.5B")
$env:COSYVOICE_REPO = (Join-Path (Split-Path -Parent $Root) "third_party\CosyVoice")
$env:COSYVOICE_STREAM_TOKEN_HOP_LEN = "20"

Write-Host "=== Xiongda CosyVoice TTS ===" -ForegroundColor Cyan
Write-Host ("Root:   {0}" -f $Root)
Write-Host ("Python: {0}" -f $Python)
Write-Host ("Device: cuda")
Write-Host ("URL:    http://127.0.0.1:{0}" -f $Port)
Write-Host ("Mode:   fp16 + TensorRT + punctuation split")
Write-Host ""

if ($Background) {
    $proc = Start-Process -FilePath $Python `
        -ArgumentList "tts_server.py" `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $LogOut `
        -RedirectStandardError $LogErr `
        -PassThru

    Write-Host ("[start] CosyVoice TTS started in background. PID={0}" -f $proc.Id) -ForegroundColor Green
    Write-Host ("[log] stdout: {0}" -f $LogOut)
    Write-Host ("[log] stderr: {0}" -f $LogErr)
    Write-Host "[wait] Loading models. This may take a while..."

    for ($i = 0; $i -lt 200; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-PortInUse $Port) {
            Show-Health -Port $Port
            return
        }
        if ($proc.HasExited) {
            Write-Host "[error] TTS process exited early. Last stderr lines:" -ForegroundColor Red
            Get-Content -LiteralPath $LogErr -Tail 100 -ErrorAction SilentlyContinue
            exit 1
        }
    }

    Write-Host "[warn] TTS is still loading or failed to bind. Check logs:" -ForegroundColor Yellow
    Write-Host $LogErr
    return
}

Write-Host "[foreground] Starting CosyVoice TTS. Press Ctrl+C to stop."
& $Python "tts_server.py"
