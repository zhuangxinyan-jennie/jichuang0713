#requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$ModelDir = Join-Path $Root "pretrained_models\CosyVoice2-0.5B"

$Py = @(
    (Join-Path $Root "bear_agent\.venv\Scripts\python.exe"),
    "D:\python3.9.0_0303\python.exe",
    "python"
) | Where-Object { $_ -eq "python" -or (Test-Path -LiteralPath $_) } | Select-Object -First 1

Write-Host ""
Write-Host "=== CosyVoice2-0.5B ===" -ForegroundColor Cyan
Write-Host "Dir:    $ModelDir"
Write-Host "Python: $Py"
Write-Host "Note:   no CosyVoice venv required; model path is fixed." -ForegroundColor DarkGray
Write-Host ""

Write-Host "[1/2] pip install modelscope tqdm ..." -ForegroundColor Yellow
& $Py -m pip install modelscope tqdm -U `
    --trusted-host pypi.org --trusted-host files.pythonhosted.org `
    --trusted-host mirrors.aliyun.com `
    -i https://mirrors.aliyun.com/pypi/simple/

Write-Host ""
Write-Host "[2/2] Downloading (watch progress bars below)..." -ForegroundColor Yellow
Write-Host ""

& $Py (Join-Path $Root "download_cosyvoice2.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[ok] Done: $ModelDir" -ForegroundColor Green
