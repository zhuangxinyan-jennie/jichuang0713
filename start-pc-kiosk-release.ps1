#requires -Version 5.1
param(
    [switch]$InstallNpm,
    [int]$Port = 4173
)

$ErrorActionPreference = "Stop"
chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$repoRoot = $PSScriptRoot
$webRoot = Join-Path $repoRoot "xiongda_app"

if (-not (Test-Path -LiteralPath $webRoot)) {
    throw "未找到 xiongda_app: $webRoot"
}

Push-Location $webRoot
try {
    if ($InstallNpm -or -not (Test-Path -LiteralPath (Join-Path $webRoot "node_modules"))) {
        Write-Host "[npm] 安装前端依赖..." -ForegroundColor Yellow
        npm install
    }

    Write-Host "[build] 生成 kiosk 发布版..." -ForegroundColor Cyan
    npm run build

    Write-Host ""
    Write-Host "[preview] 启动局域网预览: http://0.0.0.0:$Port" -ForegroundColor Green
    Write-Host "[preview] 板子 kiosk 会优先使用这个端口；Ctrl+C 可停止。" -ForegroundColor Green
    Write-Host ""

    npm run preview -- --host 0.0.0.0 --port $Port --strictPort
}
finally {
    Pop-Location
}
