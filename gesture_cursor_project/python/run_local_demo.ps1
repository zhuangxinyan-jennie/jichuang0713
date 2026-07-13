# 一键本地演示：自动使用推荐虚拟环境，无需手动 activate
$VenvPython = "f:\jichuang2026\2026--\gesture_project\venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Error @"
找不到推荐虚拟环境：
  $VenvPython

请先在 PowerShell 执行：
  cd f:\jichuang2026\2026--\gesture_project
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  pip install -r f:\jichuang2026\gesture_cursor_project\python\requirements.txt
"@
    exit 1
}
Set-Location $PSScriptRoot
& $VenvPython run_local_demo.py @args
