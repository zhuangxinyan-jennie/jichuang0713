param(
    [string]$Python = "C:\Users\tanza\anaconda3\envs\jichuang0505\python.exe",
    [string]$Text = "",
    [switch]$StreamPlay,
    [switch]$LowLatency,
    [switch]$Fp16,
    [switch]$LoadJit,
    [switch]$LoadTrt,
    [int]$StreamTokenHopLen = 20,
    [int]$SplitMinChars = 16,
    [double]$HybridPrefetchAfterSeconds = 2.0,
    [switch]$SplitPunctuation,
    [switch]$SplitSentences,
    [switch]$NoSplitSentences,
    [switch]$QueuedPlayback,
    [switch]$HybridPlayback,
    [switch]$NoStream,
    [switch]$NoProfile,
    [switch]$NoPlay
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $Root
$EnvRoot = Split-Path -Parent $Python
$ExtraDllDirs = @(
    (Join-Path $EnvRoot "bin"),
    (Join-Path $EnvRoot "Library\bin"),
    (Join-Path $EnvRoot "Scripts"),
    (Join-Path $EnvRoot "Lib\site-packages\torch\lib")
) | Where-Object { Test-Path -LiteralPath $_ }
$env:PATH = (($ExtraDllDirs + @($env:PATH)) -join [System.IO.Path]::PathSeparator)
$ArgsList = @(
    (Join-Path $Root "scripts\cosyvoice_repl.py"),
    "--preset", (Join-Path $Root "scripts\presets\xiongda_live.json"),
    "--cosyvoice-repo", (Join-Path $ProjectRoot "third_party\CosyVoice"),
    "--model-dir", (Join-Path $ProjectRoot "pretrained_models\CosyVoice2-0.5B"),
    "--output-dir", (Join-Path $Root "outputs\cosyvoice_repl"),
    "--prefix", "windows_repl"
)

if (-not $NoStream) {
    $ArgsList += "--stream"
    if ($StreamTokenHopLen -gt 0) {
        $ArgsList += @("--stream-token-hop-len", $StreamTokenHopLen.ToString([Globalization.CultureInfo]::InvariantCulture))
    }
}
if ($StreamPlay) {
    $ArgsList += "--stream-play"
}
if ($QueuedPlayback) {
    $ArgsList += "--queued-playback"
}
if ($HybridPlayback) {
    $ArgsList += "--hybrid-playback"
    $ArgsList += @("--hybrid-prefetch-after-seconds", $HybridPrefetchAfterSeconds.ToString([Globalization.CultureInfo]::InvariantCulture))
}
if ($SplitPunctuation -and -not $NoSplitSentences) {
    $ArgsList += "--split-punctuation"
} elseif ($SplitSentences -and -not $NoSplitSentences) {
    $ArgsList += "--split-sentences"
    $ArgsList += @("--split-min-chars", $SplitMinChars.ToString([Globalization.CultureInfo]::InvariantCulture))
} else {
    $ArgsList += "--no-split-sentences"
}
if ($LowLatency) {
    $ArgsList += "--low-latency"
}
if ($Fp16) {
    $ArgsList += "--fp16"
}
if ($LoadJit) {
    $ArgsList += "--load-jit"
}
if ($LoadTrt) {
    $ArgsList += "--load-trt"
}
if (-not $NoProfile) {
    $ArgsList += "--profile"
}
if ($NoPlay) {
    $ArgsList += "--no-play"
}

if ($Text.Trim().Length -gt 0) {
    $TempInput = [System.IO.Path]::GetTempFileName()
    try {
        $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($TempInput, $Text + [Environment]::NewLine, $Utf8NoBom)
        & $Python @ArgsList --input-file $TempInput
    } finally {
        Remove-Item -LiteralPath $TempInput -Force -ErrorAction SilentlyContinue
    }
} else {
    & $Python @ArgsList --interactive
}
