<#
.SYNOPSIS
  Runs the automated test suites and writes JUnit XML reports to reports\tests\.

.DESCRIPTION
  unit          no database needed
  integration   hand-written fixtures through the real SQL pipeline (schemas VP_TEST_n)
  differential  oracle vs SQL: Hypothesis random batches (schema VP_HYPO) and a real-data slice
                (needs the VOLTPROOF schema built by scripts\load.ps1 and the 2018 June-Aug file)
  e2e           Playwright drives the guided demo in Chromium against a real server (needs VOLTPROOF and
                app\web\dist); saves screenshots to docs\deliverables\screenshots
  The database must be running for integration, differential and e2e suites.

.PARAMETER Suite
  all (default) | unit | integration | differential | e2e
.PARAMETER Examples
  Number of Hypothesis examples (default 12).
#>
param(
    [ValidateSet('all', 'unit', 'integration', 'differential', 'e2e')][string]$Suite = 'all',
    [int]$Examples = 12
)

. "$PSScriptRoot\_common.ps1"
Set-Location $script:RepoRoot
$py = Join-Path $script:RepoRoot '.venv\Scripts\python.exe'
$out = Join-Path $script:RepoRoot 'reports\tests'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$env:VOLTPROOF_HYPOTHESIS_EXAMPLES = "$Examples"

$suites = if ($Suite -eq 'all') { @('unit', 'integration', 'differential', 'e2e') } else { @($Suite) }
$failed = @()
$ErrorActionPreference = 'Continue'
foreach ($s in $suites) {
    Write-Step "Suite: $s"
    & $py -m pytest "tests\$s" -q -p no:cacheprovider "--junitxml=$out\$s.xml"
    if ($LASTEXITCODE -ne 0) { $failed += $s }
}
if ($failed) { Write-Host ("FAILED suites: " + ($failed -join ', ')) -ForegroundColor Red; exit 1 }
Write-Host "All requested suites passed. Reports: reports\tests\" -ForegroundColor Green
exit 0
