<#
.SYNOPSIS
  Runs the automated test suites and writes JUnit XML reports to reports\tests\.

.DESCRIPTION
  unit          no database needed
  integration   hand-written fixtures through the real SQL pipeline (schemas VP_TEST_n)
  differential  oracle vs SQL: Hypothesis random batches (schema VP_HYPO) and a real-data slice
                (needs the VOLTPROOF schema built by scripts\load.ps1 and its files in data\raw; skips otherwise)
  e2e           Playwright drives the guided demo in Chromium against a real server (needs a built schema and
                app\web\dist); saves screenshots to docs\deliverables\screenshots, or to
                reports\screenshots-synthetic on the SYNTHETIC demo set
  The database must be running for integration, differential and e2e suites.
  Schema: VOLTPROOF_SCHEMA if set, else VOLTPROOF if built, else VOLTPROOF_DEMO (the synthetic demo set).

.PARAMETER Suite
  all (default) | unit | integration | differential | e2e
.PARAMETER Examples
  Number of Hypothesis examples (default 12).
.PARAMETER Part
  Optional: run only part of one suite, as a pytest path inside tests\<Suite>, for example
  test_real_slice.py or "test_real_slice.py::test_sql_matches_oracle_on_real_up_slice". Each part writes its
  own JUnit file (<suite>+<part>.xml); pipeline\test_report.py merges the parts of a suite.
#>
param(
    [ValidateSet('all', 'unit', 'integration', 'differential', 'e2e')][string]$Suite = 'all',
    [int]$Examples = 12,
    [string]$Part = ''
)

. "$PSScriptRoot\_common.ps1"
Set-Location $script:RepoRoot
$py = Join-Path $script:RepoRoot '.venv\Scripts\python.exe'
$out = Join-Path $script:RepoRoot 'reports\tests'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$env:VOLTPROOF_HYPOTHESIS_EXAMPLES = "$Examples"

if ($Part -and $Suite -eq 'all') { throw "-Part needs a single -Suite" }
if ($Suite -ne 'unit') { $null = Resolve-VoltProofSchema }  # the app/report/e2e tests use this schema
$suites = if ($Suite -eq 'all') { @('unit', 'integration', 'differential', 'e2e') } else { @($Suite) }
$tag = if ($Part) { '+' + ($Part -replace '[^A-Za-z0-9_.-]', '_') } else { '' }
$failed = @()
$ErrorActionPreference = 'Continue'
# Run metadata for docs\TEST_REPORT.md (pipeline\test_report.py): the tested commit and whether the tree was clean
$meta = [ordered]@{
    commit = (git rev-parse HEAD 2>$null); uncommitted_files = @(git status --porcelain --untracked-files=no 2>$null).Count
    started = (Get-Date).ToString('s'); suites = $suites; part = $Part; hypothesis_examples = $Examples
    schema = $(if ($env:VOLTPROOF_SCHEMA) { $env:VOLTPROOF_SCHEMA } else { 'VOLTPROOF' })
}
foreach ($s in $suites) {
    Write-Step "Suite: $s$(if ($Part) { " (part: $Part)" })"
    $t0 = Get-Date
    $target = if ($Part) { "tests\$s\$Part" } else { "tests\$s" }
    & $py -m pytest $target -q -p no:cacheprovider "--junitxml=$out\$s$tag.xml"
    if ($LASTEXITCODE -ne 0) { $failed += $s }
    $meta["wall_seconds_$s"] = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
}
$meta.finished = (Get-Date).ToString('s'); $meta.failed = $failed
$meta | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $out "run_meta_$Suite$tag.json")
if ($failed) { Write-Host ("FAILED suites: " + ($failed -join ', ')) -ForegroundColor Red; exit 1 }
Write-Host "All requested suites passed. Reports: reports\tests\" -ForegroundColor Green
exit 0
