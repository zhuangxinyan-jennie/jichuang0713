#requires -Version 5.1
# Stop Agent/TTS/Vite (common ports) then start start-dev-stack.ps1
param([switch]$KillOnly)
$ErrorActionPreference = 'Continue'

function Stop-OnPort([int]$Port) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            $ownPid = $c.OwningProcess
            if ($ownPid -and $ownPid -ne 0) {
                Write-Host "[stop] port $Port PID $ownPid"
                Stop-Process -Id $ownPid -Force -ErrorAction SilentlyContinue
            }
        }
    }
    catch {}
}

Stop-OnPort 8765
Stop-OnPort 9888
Stop-OnPort 5173
Stop-OnPort 5174

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and (
        $_.CommandLine -like '*integration_test*server.py*' -or
        $_.CommandLine -like '*tts_server.py*' -or
        $_.CommandLine -like '*board_bridge.run_pipeline*' -or
        ($_.CommandLine -like '*vite*' -and $_.CommandLine -like '*xiongda_app*')
    )
} | ForEach-Object {
    Write-Host "[stop] $($_.Name) PID $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 1
if ($KillOnly) {
    Write-Host '[done] Kill-only finished.'
    exit 0
}
Write-Host '[start] launching start-dev-stack.ps1 ...'
& (Join-Path $PSScriptRoot 'start-dev-stack.ps1') @args
