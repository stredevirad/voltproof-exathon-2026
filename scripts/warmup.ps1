<#
.SYNOPSIS
  Prepares a live demo: warms the database for the guided demo path and pre-renders its evidence report.

.DESCRIPTION
  Run after scripts\exa.ps1 start, and again after any rebuild (scripts\load.ps1 or a SQL step). It runs the
  guided demo's queries once (home, location, month, day, event, shared-event group), so the first day view after
  a database start is not slow, and renders the demo's evidence report. The app serves that pre-rendered report
  only while its data and code are unchanged (otherwise it renders a fresh one), and shows when it was generated.
  It runs no SQL build step. Timings are written to reports\warmup.json.
  Docs: docs\deliverables\LIVE_DEMO_RUNBOOK.md
#>
. "$PSScriptRoot\_common.ps1"
Set-Location $script:RepoRoot
$py = Join-Path $script:RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw 'Python environment missing. Run scripts\bootstrap.ps1 first.' }

Write-Step 'Checking the database'
$status = Get-DatabaseStatus
if ($status -notmatch 'database_ready') {
    Write-Host $status
    throw 'Exasol is not ready. Start it with: scripts\exa.ps1 start'
}

$null = Resolve-VoltProofSchema
Write-Step 'Warming the guided demo path and pre-rendering its report'
$ErrorActionPreference = 'Continue'
& $py -m pipeline.warmup
exit $LASTEXITCODE
