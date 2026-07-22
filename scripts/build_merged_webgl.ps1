# Build merged WebGL -> xiongda_app/public/webgl-merged/
# Usage (from clean_0606 root):
#   powershell -ExecutionPolicy Bypass -File .\scripts\build_merged_webgl.ps1
# Optional: set UNITY_EXE to your Unity.exe path

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$projectPath = Join-Path $repoRoot "XiongdaParkMapMergedProject"
$logFile = Join-Path $repoRoot "XiongdaParkMapMergedProject\Logs\build_merged_webgl.log"
$outDir = Join-Path $repoRoot "xiongda_app\public\webgl-merged"

if (-not (Test-Path $projectPath)) {
    Write-Error "Merged project not found: $projectPath (run setup_merged_unity_project.ps1 first)"
}

$unityExe = $env:UNITY_EXE
if (-not $unityExe) {
    $candidates = @(
        "F:\APPS\Unity\2018.4.35f1\Editor\Unity.exe",
        "C:\Program Files\Unity\Hub\Editor\2018.4.35f1\Editor\Unity.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $unityExe = $c; break }
    }
}
if (-not $unityExe -or -not (Test-Path $unityExe)) {
    Write-Error "Unity.exe not found. Set UNITY_EXE or install Unity 2018.4.35f1"
}

$logDir = Split-Path $logFile -Parent
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

Write-Host "Unity: $unityExe"
Write-Host "Project: $projectPath"
Write-Host "Log: $logFile"
Write-Host "Output: $outDir"
Write-Host ""
Write-Host "Building Development WebGL (may take 10-40 min)..."

$unityArgs = @(
    "-batchmode",
    "-nographics",
    "-quit",
    "-projectPath", $projectPath,
    "-executeMethod", "SmartParkTerminal.EditorTools.MergedProjectSetupMenu.BuildMergedWebGLDevelopment",
    "-logFile", $logFile
)

$p = Start-Process -FilePath $unityExe -ArgumentList $unityArgs -Wait -PassThru -NoNewWindow
if ($p.ExitCode -ne 0) {
    Write-Host ""
    Write-Host "Unity exit code: $($p.ExitCode). See log:" -ForegroundColor Red
    Write-Host $logFile
    if (Test-Path $logFile) {
        $tail = Get-Content $logFile -Tail 30 -ErrorAction SilentlyContinue
        if ($tail -match "another Unity instance") {
            Write-Host ""
            Write-Host "Hint: close Unity Hub/Editor for this project, then rerun this script." -ForegroundColor Yellow
            Write-Host "Or use menu: Tools -> build merged WebGL (Development) to webgl-merged"
        }
    }
    exit $p.ExitCode
}

$buildInfo = Join-Path $outDir "build-info.json"
if (-not (Test-Path $buildInfo)) {
    Write-Host ""
    Write-Host "Build finished but build-info.json missing (IL2CPP may have failed). See log." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "OK -> $outDir" -ForegroundColor Green
Write-Host "Next: cd xiongda_app; npm run dev; open tab World Interaction"
