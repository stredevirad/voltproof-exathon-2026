<#
.SYNOPSIS
  Verifies the raw ESMI files, loads them into Exasol and runs the whole analytical pipeline in SQL.

.DESCRIPTION
  1. scripts\get-data.ps1 -Set <Set>  (checksums against Harvard Dataverse; writes data\manifest.json)
  2. Native IMPORT of every verified file into the raw tables (schema VOLTPROOF by default)
  3. SQL steps 020-095 inside Exasol (unpivot, cleaning, segments, events, aggregates, quality),
     one transaction per step, provenance in RUN_LOG
  4. Fails if a file is mostly quarantined (a sign that its layout changed)

  The database must be running: scripts\exa.ps1 status  (start it with scripts\exa.ps1 start).

.PARAMETER Set
  Which files must be present and verified: first | up | all (see scripts\get-data.ps1). Default: up.
#>
param(
    [ValidateSet('first', 'up', 'all')][string]$Set = 'up',
    [string]$Schema = 'VOLTPROOF',
    [switch]$SkipLoad
)

. "$PSScriptRoot\_common.ps1"
Set-Location $script:RepoRoot
$py = Join-Path $script:RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Python environment missing. Run scripts\bootstrap.ps1 first." }

Write-Step "Checking that the database is ready"
$status = (& "$PSScriptRoot\exa.ps1" status) -join "`n"
if ($status -notmatch 'database_ready') {
    throw "Exasol is not ready. Start it with: scripts\exa.ps1 start`n$status"
}

if (-not $SkipLoad) {
    & "$PSScriptRoot\get-data.ps1" -Set $Set
    if ($LASTEXITCODE -ne 0) { throw "Raw files missing or not verified for set '$Set' (see above)." }
}

Write-Step "Loading and building schema $Schema"
$ErrorActionPreference = 'Continue'
$argsList = @('-m', 'pipeline.build', '--schema', $Schema)
if ($SkipLoad) { $argsList += '--skip-load' }
& $py @argsList
$code = $LASTEXITCODE
if ($code -ne 0) { Write-Host "Build failed (exit $code)." -ForegroundColor Red; exit $code }

Write-Step "Checking provenance against Exasol's audit log"
& $py -m pipeline.check_provenance $Schema | Select-Object -Last 1
exit $LASTEXITCODE
