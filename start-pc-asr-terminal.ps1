#requires -Version 5.1
$ErrorActionPreference = "Stop"
chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Bundle = Join-Path $Root "pre_on_board_local_start_bundle"
$Py = Join-Path $Root "bear_agent\.venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

netsh advfirewall firewall add rule name="Xiongda ASR TCP 18083" dir=in action=allow protocol=TCP localport=18083 2>$null | Out-Null

$Script = Join-Path $Bundle "board_deploy\run_pc_asr_terminal.py"
& $Py $Script
