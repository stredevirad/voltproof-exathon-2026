<#
.SYNOPSIS
  Loads data into Exasol and runs the whole analytical pipeline in SQL.

.DESCRIPTION
  -Set demo     the SYNTHETIC demo set: no download. pipeline\synthetic.py writes invented monitors in the ESMI
                file format to data\demo\, and they are built into their own schema VOLTPROOF_DEMO (D-033).
  -Set first|up|all   real ESMI data:
  1. scripts\get-data.ps1 -Set <Set>  (checksums against Harvard Dataverse; writes data\manifest.json)
  2. Native IMPORT of every verified file into the raw tables (schema VOLTPROOF by default)
  3. SQL steps 020-100 inside Exasol (unpivot, cleaning, segments, events, aggregates, quality, coincidence),
     one transaction per step, provenance in RUN_LOG
  4. Fails if a file is mostly quarantined (a sign that its layout changed)
  Synthetic and real data never share a schema; the build refuses to mix them.

  The database must be running: scripts\exa.ps1 status  (start it with scripts\exa.ps1 start).

.PARAMETER Set
  demo | first | up | all (see scripts\get-data.ps1 for the real sets). Default: up.
#>
param(
    [ValidateSet('demo', 'first', 'up', 'all')][string]$Set = 'up',
    [string]$Schema = '',
    [switch]$SkipLoad
)

. "$PSScriptRoot\_common.ps1"
Set-Location $script:RepoRoot
$py = Join-Path $script:RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Python environment missing. Run scripts\bootstrap.ps1 first." }

if ($Set -eq 'demo') {
    if (-not $Schema) { $Schema = 'VOLTPROOF_DEMO' }
    if ($env:VOLTPROOF_SCHEMA -and $env:VOLTPROOF_SCHEMA.ToUpper() -ne $Schema.ToUpper()) {
        throw "VOLTPROOF_SCHEMA is '$($env:VOLTPROOF_SCHEMA)', but the synthetic demo set builds into $Schema. Clear it first: Remove-Item Env:VOLTPROOF_SCHEMA"
    }
    if ($Schema.ToUpper() -eq 'VOLTPROOF') { throw 'The synthetic demo set never goes into VOLTPROOF (the real-data schema).' }
} elseif (-not $Schema) {
    $Schema = if ($env:VOLTPROOF_SCHEMA) { $env:VOLTPROOF_SCHEMA } else { 'VOLTPROOF' }
}

Write-Step "Checking that the database is ready"
$status = Get-DatabaseStatus
if ($status -notmatch 'database_ready') {
    throw "Exasol is not ready. Start it with: scripts\exa.ps1 start`n$status"
}

if ($Set -ne 'demo' -and -not $SkipLoad) {
    & "$PSScriptRoot\get-data.ps1" -Set $Set
    if ($LASTEXITCODE -ne 0) { throw "Raw files missing or not verified for set '$Set' (see above)." }
}

Write-Step "Loading and building schema $Schema$(if ($Set -eq 'demo') { ' (SYNTHETIC demo data)' })"
$ErrorActionPreference = 'Continue'
$argsList = @('-m', 'pipeline.build', '--schema', $Schema)
if ($Set -eq 'demo') { $argsList += '--demo' }
if ($SkipLoad) { $argsList += '--skip-load' }
& $py @argsList
$code = $LASTEXITCODE
if ($code -ne 0) { Write-Host "Build failed (exit $code)." -ForegroundColor Red; exit $code }

Write-Step "Checking provenance against Exasol's audit log"
& $py -m pipeline.check_provenance $Schema | Select-Object -Last 1
exit $LASTEXITCODE
