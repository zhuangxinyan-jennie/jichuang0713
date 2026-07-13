#requires -Version 5.1

param([switch]$RecreateVenv, [switch]$CreateCondaEnv)

$ErrorActionPreference = "Stop"

chcp 65001 | Out-Null

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8



$Root = $PSScriptRoot

$Repo = Join-Path $Root "third_party\CosyVoice"

$Venv = Join-Path $Repo ".venv-clean"

$WinReq = Join-Path $Root "cosyvoice-requirements-windows.txt"

$CondaEnvName = "jichuang-cosyvoice"

$PipIndex = "https://mirrors.aliyun.com/pypi/simple/"

$pipTrust = @("--trusted-host","pypi.org","--trusted-host","files.pythonhosted.org","--trusted-host","mirrors.aliyun.com","--trusted-host","pypi.tuna.tsinghua.edu.cn","--trusted-host","download.pytorch.org")



function Get-PyVer { param([string]$Exe)

    $v = & $Exe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"

    if ($LASTEXITCODE -ne 0) { return $null }; return $v.Trim()

}

function Resolve-Python310 {

    $candidates = @()

    if ($env:COSYVOICE_PY -and (Test-Path -LiteralPath $env:COSYVOICE_PY)) { $candidates += $env:COSYVOICE_PY }

    $condaPy = Join-Path $env:USERPROFILE ".conda\envs\$CondaEnvName\python.exe"

    if (Test-Path -LiteralPath $condaPy) { $candidates += $condaPy }

    foreach ($ver in @("3.10","3.11","3.12")) {

        try { $out = & py "-$ver" -c "import sys; print(sys.executable)" 2>$null

            if ($LASTEXITCODE -eq 0 -and $out) { $candidates += $out.Trim() }

        } catch {}

    }

    foreach ($exe in $candidates | Select-Object -Unique) {

        $mm = Get-PyVer $exe

        if ($mm -and [version]$mm -ge [version]"3.10") { return $exe }

    }

    if ($CreateCondaEnv) {

        Write-Host "[conda] Creating $CondaEnvName (Python 3.10)..." -ForegroundColor Yellow

        $null = & conda create -n $CondaEnvName python=3.10 -y 2>&1

        if ($LASTEXITCODE -ne 0) { throw "conda create failed" }

        if (Test-Path -LiteralPath $condaPy) { return $condaPy }

    }

    return $null

}

function Invoke-PipStep { param([string]$Label, [string[]]$PipArgs)

    Write-Host $Label -ForegroundColor Yellow

    & $venvPy -m pip @PipArgs

    if ($LASTEXITCODE -ne 0) { throw "pip failed: $Label (exit $LASTEXITCODE)" }

}



if (-not (Test-Path (Join-Path $Repo "requirements.txt"))) { throw "CosyVoice source not found: $Repo" }

Write-Host "`n=== CosyVoice venv setup (clean_0606) ===" -ForegroundColor Cyan

Write-Host "Target: $Venv"

Write-Host "Ref: cozy_ref (read-only reference, not install path)`n"



$Py = Resolve-Python310

if (-not $Py) {

    Write-Host "[FAILED] Need Python 3.10+ (teammate cosy_ref README)." -ForegroundColor Red

    Write-Host "Run: .\setup-cosyvoice-venv.ps1 -CreateCondaEnv -RecreateVenv"

    exit 1

}

Write-Host ("Base Python: {0} ({1})" -f $Py, (Get-PyVer $Py)) -ForegroundColor Gray



$venvPy = Join-Path $Venv "Scripts\python.exe"

if ($RecreateVenv -and (Test-Path $Venv)) { Remove-Item -LiteralPath $Venv -Recurse -Force }

if (Test-Path -LiteralPath $venvPy) {

    $venvVer = Get-PyVer $venvPy

    if ($venvVer -and [version]$venvVer -lt [version]"3.10") { Remove-Item -LiteralPath $Venv -Recurse -Force }

}

if (-not (Test-Path -LiteralPath $venvPy)) { & $Py -m venv $Venv; if ($LASTEXITCODE -ne 0) { throw "venv creation failed" } }



try {

    Invoke-PipStep "[1/5] pip / setuptools / wheel" @("install","-U","pip","setuptools<81","wheel","-i",$PipIndex) + $pipTrust

    Invoke-PipStep "[2/5] torch + torchaudio (CUDA 12.1)" @("install","torch==2.3.1","torchaudio==2.3.1","--index-url","https://download.pytorch.org/whl/cu121") + $pipTrust

    Invoke-PipStep "[3/5] CosyVoice deps (Windows list)" @("install","-r",$WinReq,"-i",$PipIndex) + $pipTrust

    Invoke-PipStep "[4/5] openai-whisper (--no-build-isolation)" @("install","openai-whisper==20231117","--no-build-isolation","-i",$PipIndex) + $pipTrust

    if ($env:INSTALL_VLLM -eq "1") {

        Invoke-PipStep "[5/5] vllm + transformers + numpy" @("install","vllm==0.9.0","transformers==4.51.3","numpy==1.26.4","-i",$PipIndex) + $pipTrust

    } else {

        Write-Host "[5/5] skip vllm on Windows" -ForegroundColor DarkGray

        Invoke-PipStep "[5/5] transformers + numpy" @("install","transformers==4.51.3","numpy==1.26.4","-i",$PipIndex) + $pipTrust

    }

    $env:PYTHONPATH = $Repo

    & $venvPy -c "import sys; sys.path.insert(0, r'$Repo'); import conformer, torch, cosyvoice, whisper; print('verify ok', torch.__version__)"

    if ($LASTEXITCODE -ne 0) { throw "import verify failed" }

    Write-Host "`n[OK] CosyVoice venv ready: $venvPy" -ForegroundColor Green

    Write-Host "Next: .\check-cosyvoice-env.ps1" -ForegroundColor Yellow

} catch {

    Write-Host "`n[FAILED] CosyVoice venv NOT ready." -ForegroundColor Red

    Write-Host $_.Exception.Message -ForegroundColor Red

    exit 1

}


