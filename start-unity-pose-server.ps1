#requires -Version 5.1
# 启动 MediaPipe Pose 服务，供 Unity XiongdaRealtimeCameraArmSync 轮询 /api/pose
$ErrorActionPreference = "Stop"
chcp 65001 | Out-Null

$PoseDir = Join-Path $PSScriptRoot "gesture_cursor_project\python"
$Candidates = @(
    "f:\jichuang2026\2026--\gesture_project\venv\Scripts\python.exe",
    (Join-Path $PSScriptRoot "bear_agent\.venv\Scripts\python.exe"),
    "python"
)

$Python = $null
foreach ($c in $Candidates) {
    if ($c -eq "python") {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) { $Python = $cmd.Source; break }
        continue
    }
    if (Test-Path $c) { $Python = $c; break }
}

if (-not $Python) {
    Write-Error "Python not found. Install gesture_project venv or bear_agent\.venv"
}

Write-Host "Pose service: http://127.0.0.1:8767/api/pose" -ForegroundColor Cyan
Write-Host "Unity: SmartParkTerminal -> Play -> enable Realtime Camera Arm Sync" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""

Set-Location $PoseDir
& $Python run_pose_server.py --camera 0 --preview @args
