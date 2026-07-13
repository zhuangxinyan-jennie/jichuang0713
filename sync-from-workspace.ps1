#requires -Version 5.1
<#
 将工作区项目同步到本仓库根目录下的子文件夹（用于一次性提交到 jichuang0505）。
 默认源路径在 $WorkspaceRoot；可按机器修改。
#>
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$WorkspaceRoot = if ($env:JICHUANG2026_ROOT) { $env:JICHUANG2026_ROOT.TrimEnd('\') } else { "F:\jichuang2026" }

$map = @(
    @{ Name = "bear_agent";           Source = Join-Path $WorkspaceRoot "bear_agent" }
    @{ Name = "xiongda_app";          Source = Join-Path $WorkspaceRoot "xiongda_app" }
    @{ Name = "XiongdaUnityProject";  Source = Join-Path $WorkspaceRoot "unity_model\XiongdaUnityProject" }
    @{ Name = "pre_on_board_local_start_bundle"; Source = Join-Path $WorkspaceRoot "pre_board\pre_on_board_local_start_bundle.tar\pre_on_board_local_start_bundle.tar\pre_on_board_local_start_bundle" }
)

$xd = @(
    ".git", ".venv", "node_modules", "__pycache__", ".conda_env",
    "Library", "Temp", "Logs", "obj", "Bin", ".vs", ".gradle",
    "tts_outputs", "pc_received_output"
)

Write-Host "Repo root:     $RepoRoot" -ForegroundColor Cyan
Write-Host "Workspace root: $WorkspaceRoot" -ForegroundColor Cyan

foreach ($item in $map) {
    $src = $item.Source
    $name = $item.Name
    $dst = Join-Path $RepoRoot $name
    if (-not (Test-Path -LiteralPath $src)) {
        Write-Host "[SKIP] 源不存在: $src" -ForegroundColor Yellow
        continue
    }
    Write-Host "[SYNC] $name" -ForegroundColor Green
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    $argXd = ($xd | ForEach-Object { "/XD", $_ })
    $args = @($src, $dst, "/MIR", "/E") + $argXd + @("/XF", "xiongda_portable.zip") + @("/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np")
    $rc = Start-Process -FilePath "robocopy.exe" -ArgumentList $args -Wait -PassThru -NoNewWindow
    if ($rc.ExitCode -ge 8) {
        throw "robocopy failed for $name exit=$($rc.ExitCode)"
    }
}

Write-Host "`nDone. Next: cd `"$RepoRoot`"; git add -A; git commit -m `"sync workspace`"; git push" -ForegroundColor Cyan
