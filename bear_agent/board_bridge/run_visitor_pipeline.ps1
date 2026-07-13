# PC 摄像头 + 麦克风 → 310B → board_bridge → Bear Agent（Windows）
# 用法（PowerShell）：
#   $env:BEAR_BOARD_HOST = "192.168.1.100"
#   $env:PRE_BOARD_ROOT = "F:\path\to\pre_on_board_local_start_bundle"
#   .\board_bridge\run_visitor_pipeline.ps1
#
# 另开两个终端：python integration_test\server.py ； cd ..\xiongda_app ; npm run dev

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
if (-not $env:BEAR_BOARD_HOST) {
    Write-Host "请先设置环境变量 BEAR_BOARD_HOST（板子 IP）" -ForegroundColor Red
    exit 2
}
if (-not $env:PRE_BOARD_ROOT) {
    Write-Host "请先设置 PRE_BOARD_ROOT（解压后的本地启动包根目录，含 board_deploy）" -ForegroundColor Red
    exit 2
}

python -m board_bridge.run_visitor_pipeline @args
