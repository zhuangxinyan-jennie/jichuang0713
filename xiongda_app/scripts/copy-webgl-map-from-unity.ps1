# 将 Unity 地图 WebGL 构建输出复制到 public/webgl-map
# 用法：powershell -ExecutionPolicy Bypass -File .\scripts\copy-webgl-map-from-unity.ps1

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = Join-Path $here "..\public\webgl-map"

Write-Host "=== 复制地图 Unity WebGL 到 public/webgl-map ===" -ForegroundColor Cyan
$src = Read-Host "请粘贴 Unity Build 输出的文件夹路径（里面有 Build 子文件夹）"

if (-not (Test-Path $src)) {
    Write-Host "路径不存在: $src" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $dest | Out-Null

foreach ($n in @("Build", "TemplateData", "StreamingAssets")) {
    $p = Join-Path $dest $n
    if (Test-Path $p) {
        Remove-Item $p -Recurse -Force
    }
}

Copy-Item -Path (Join-Path $src "*") -Destination $dest -Recurse -Force

Write-Host "`n复制完成。" -ForegroundColor Green
Write-Host "若还没有 build-info.json：复制 public/webgl-map/build-info.example.json 为 build-info.json" -ForegroundColor Yellow
