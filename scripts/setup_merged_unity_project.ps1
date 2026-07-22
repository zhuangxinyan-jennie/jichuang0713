#requires -Version 5.1
<#
.SYNOPSIS
  Create XiongdaParkMapMergedProject from ParkMap + bear SMPL/face scripts.
  Does NOT modify or overwrite XiongdaUnityProject / XiongdaParkMapProject.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\setup_merged_unity_project.ps1
#>
param(
    [switch]$ForceRecreate
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
# scripts/ → repo root
$Root = Split-Path -Parent $Root
$Park = Join-Path $Root "XiongdaParkMapProject"
$Bear = Join-Path $Root "XiongdaUnityProject"
$Merged = Join-Path $Root "XiongdaParkMapMergedProject"

if (-not (Test-Path -LiteralPath $Park)) { throw "Missing $Park" }
if (-not (Test-Path -LiteralPath $Bear)) { throw "Missing $Bear" }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Setup MERGED Unity project (safe copy)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Source map : $Park"
Write-Host "Source bear: $Bear"
Write-Host "Output     : $Merged"
Write-Host "Originals are left untouched."
Write-Host ""

if ((Test-Path -LiteralPath $Merged) -and $ForceRecreate) {
    Write-Host "[warn] -ForceRecreate: removing old merged folder..." -ForegroundColor Yellow
    Remove-Item -LiteralPath $Merged -Recurse -Force
}

if (-not (Test-Path -LiteralPath $Merged)) {
    Write-Host "[1/4] Copying ParkMap (exclude Library/Temp/Logs/Obj) ..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $Merged | Out-Null
    $xd = @(
        "Library", "Temp", "Logs", "Obj", "obj",
        ".vs", ".idea", "*.csproj", "*.sln", "*.userprefs"
    )
    # robocopy: exclude dirs
    $rcArgs = @(
        $Park, $Merged, "/E", "/XD", "Library", "Temp", "Logs", "Obj", "obj", ".vs",
        "/XF", "*.csproj", "*.sln", "*.userprefs", "*.pidb",
        "/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np"
    )
    & robocopy @rcArgs
    # robocopy exit codes 0-7 are success-ish
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed exit=$LASTEXITCODE" }
    Write-Host "      OK base copy" -ForegroundColor Green
} else {
    Write-Host "[1/4] Merged folder already exists — skip full copy (use -ForceRecreate to wipe)" -ForegroundColor DarkGray
}

function Copy-BearItem {
    param([string]$RelPath)
    $src = Join-Path $Bear $RelPath
    $dst = Join-Path $Merged $RelPath
    if (-not (Test-Path -LiteralPath $src)) {
        Write-Host "      skip missing $RelPath" -ForegroundColor DarkYellow
        return
    }
    $dstDir = Split-Path -Parent $dst
    New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
    if (Test-Path -LiteralPath $src -PathType Container) {
        & robocopy $src $dst /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    } else {
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }
    Write-Host "      + $RelPath" -ForegroundColor Green
}

Write-Host "[2/4] Copy bear SMPL / face / bridge scripts ..." -ForegroundColor Yellow
$scriptFiles = @(
    "Assets\Scripts\SmplhMotionRetarget.cs",
    "Assets\Scripts\XiongdaSmplhMotionDirector.cs",
    "Assets\Scripts\XiongdaFaceBlendShapeDriver.cs",
    "Assets\Scripts\XiongdaLegacyAnimationDirector.cs",
    "Assets\Scripts\SmartParkTerminal\UnityBridge.cs",
    "Assets\Scripts\SmartParkTerminal\ClipIdPlayer.cs",
    "Assets\Scripts\SmartParkTerminal\ReactEmbedModeBootstrap.cs"
)
foreach ($f in $scriptFiles) { Copy-BearItem $f }

# meta files if present (Unity GUID stability optional)
foreach ($f in $scriptFiles) {
    $meta = "$f.meta"
    if (Test-Path (Join-Path $Bear $meta)) { Copy-BearItem $meta }
}

Write-Host "[3/4] Copy StreamingAssets/SmplhRetarget ..." -ForegroundColor Yellow
Copy-BearItem "Assets\StreamingAssets\SmplhRetarget"
if (Test-Path (Join-Path $Bear "Assets\StreamingAssets\SmplhRetarget.meta")) {
    Copy-BearItem "Assets\StreamingAssets\SmplhRetarget.meta"
}

Write-Host "[3.2/4] Copy interactive bear model (xiongda.fbx + face rig) ..." -ForegroundColor Yellow
Copy-BearItem "Assets\XiongdaImported\xiongda_base_default\xiongda_maybe_final_new"

# Editor helpers from bear if useful
if (Test-Path (Join-Path $Bear "Assets\Editor\SmplhCalibrationHelper.cs")) {
    Copy-BearItem "Assets\Editor\SmplhCalibrationHelper.cs"
}

Write-Host "[3.5/4] Copy merged overlay scripts (bridges + editor menus) ..." -ForegroundColor Yellow
$overlay = Join-Path $Root "scripts\unity_merged_overlay"
if (Test-Path -LiteralPath $overlay) {
    & robocopy (Join-Path $overlay "Assets") (Join-Path $Merged "Assets") /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    Write-Host "      OK overlay" -ForegroundColor Green
} else {
    Write-Host "      WARN overlay missing: $overlay" -ForegroundColor DarkYellow
}

$readme = @"
# XiongdaParkMapMergedProject（合并工程 · 可回退）

## 目的
一个 WebGL 里：熊大既能聊天表演（表情 / SMPL），又能在乐园地图里走路导航。

## 安全回退
- **原工程未改**：``XiongdaUnityProject``、``XiongdaParkMapProject``
- 前端默认仍可用双包 ``/webgl`` + ``/webgl-map``
- 合并产物请打到 ``xiongda_app/public/webgl-merged/``（不要覆盖旧两包）

## 你在 Unity 里要做的（阶段 1）
1. Unity Hub 打开本目录（2018.4.x）
2. 打开场景 ``Assets/Scenes/ParkMap3DBlockout.unity``
3. 菜单：**Tools → 狗熊岭智慧终端 → 合并工程：挂上 UnityBridge + 模式相机**
4. 在熊大物体上检查是否有 ``SmplhMotionRetarget`` / ``XiongdaFaceBlendShapeDriver``（没有则按语音工程同款挂上）
5. 菜单：**Tools → 狗熊岭智慧终端 → 构建合并 WebGL 到 xiongda_app/webgl-merged**

## 重建本文件夹
``````powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_merged_unity_project.ps1 -ForceRecreate
``````
"@
Set-Content -LiteralPath (Join-Path $Merged "README_MERGED.md") -Value $readme -Encoding UTF8

Write-Host ""
Write-Host "DONE. Open in Unity Hub: $Merged" -ForegroundColor Green
Write-Host "Originals untouched: XiongdaUnityProject / XiongdaParkMapProject" -ForegroundColor Green
