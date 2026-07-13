#requires -Version 5.1
<#
.SYNOPSIS
  实时查看 Agent 推理 + TTS 延时（latency_live.log）。
.DESCRIPTION
  若文件不存在会自动创建空文件并监听；真正有内容需 Bear Agent / TTS / board_bridge
  启动时已设置 BEAR_LATENCY_LOG=1 且 BEAR_LATENCY_LOG_FILE 指向该路径。
  推荐：.\scripts\start-dev-stack.ps1 -LatencyLog（会自动创建并弹出窗口）。
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\watch-latency-live.ps1
#>
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dir = Join-Path $root "logs\dev-stack"
$path = Join-Path $dir "latency_live.log"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
if (-not (Test-Path -LiteralPath $path)) {
    New-Item -ItemType File -Path $path -Force | Out-Null
    Write-Host "已创建空日志: $path" -ForegroundColor Yellow
    Write-Host "请用 start-dev-stack.ps1 -LatencyLog 重启 Agent/TTS，或手动设置 BEAR_LATENCY_LOG=1 后再操作。" -ForegroundColor Yellow
    Write-Host ""
}
Write-Host "监听延时日志（Ctrl+C 退出）: $path" -ForegroundColor Cyan
Get-Content -LiteralPath $path -Wait -Encoding UTF8
