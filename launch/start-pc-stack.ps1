#requires -Version 5.1
param([switch]$SkipTts, [switch]$InstallNpm)
$ErrorActionPreference = "Stop"
chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $RepoRoot "env.local.ps1")
$stack = Join-Path $RepoRoot "xiongda_app\scripts\start-dev-stack.ps1"

# Call dev stack directly — do NOT spawn a nested powershell.exe.
# Nested PowerShell loads conda profile and can crash with GBK/Unicode on PATH.
$stackArgs = @{}
if ($SkipTts) { $stackArgs.SkipTts = $true }
if ($InstallNpm) { $stackArgs.InstallNpm = $true }
& $stack @stackArgs

