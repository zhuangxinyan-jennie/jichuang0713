#requires -Version 5.1
param([switch]$SkipTts, [switch]$InstallNpm)
$ErrorActionPreference = "Stop"
chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

. (Join-Path $PSScriptRoot "env.local.ps1")
$stack = Join-Path $PSScriptRoot "xiongda_app\scripts\start-dev-stack.ps1"

# Call dev stack directly — do NOT spawn a nested powershell.exe.
# Nested PowerShell loads conda profile and can crash with GBK/Unicode on PATH.
$stackArgs = @{}
if ($SkipTts) { $stackArgs.SkipTts = $true }
if ($InstallNpm) { $stackArgs.InstallNpm = $true }
& $stack @stackArgs
