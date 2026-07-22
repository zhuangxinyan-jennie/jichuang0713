$paths = @(
  "F:\jichuang2026\clean_0606\start-full-demo.ps1",
  "F:\jichuang2026\clean_0606\stop-full-demo.ps1"
)
foreach ($p in $paths) {
  $tokens = $null
  $errs = $null
  [void][System.Management.Automation.Language.Parser]::ParseFile($p, [ref]$tokens, [ref]$errs)
  if ($errs -and $errs.Count -gt 0) {
    Write-Host "FAIL $p"
    $errs | ForEach-Object { Write-Host $_.ToString() }
    exit 1
  }
  Write-Host "OK $p"
}
