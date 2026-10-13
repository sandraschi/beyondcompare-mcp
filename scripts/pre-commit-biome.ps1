# Fleet local biome hook: runs `bun run biome:ci` in whichever web root exists.
$ErrorActionPreference = "Stop"

function Find-Bun {
  $cmd = Get-Command "bun" -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $fallback = Join-Path $env:USERPROFILE ".bun\bin\bun.exe"
  if (Test-Path -LiteralPath $fallback) { return $fallback }
  return $null
}

$bun = Find-Bun
if (-not $bun) { Write-Host "biome hook: bun not found, skipping."; exit 0 }

$repoRoot = Split-Path -Parent $PSScriptRoot
$candidates = @("web_sota", "webapp", "webapp/frontend", "web", "web_sota/frontend")
$roots = @()
foreach ($rel in $candidates) {
  $full = Join-Path $repoRoot $rel
  if (Test-Path -LiteralPath $full) { $roots += $full }
}
if ($roots.Count -eq 0) { Write-Host "biome hook: no web root, skipping."; exit 0 }

foreach ($dir in $roots) {
  Push-Location -LiteralPath $dir
  try {
    & $bun run biome:ci
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  } finally {
    Pop-Location
  }
}
