<#
.SYNOPSIS
  Starts the VoltProof web app (API + built frontend in one process) and prints its URL.

.DESCRIPTION
  1. Checks that Exasol is running (scripts\exa.ps1 status shows database_ready) and that the analysis tables
     exist (built by scripts\load.ps1).
  2. Builds the web app into app\web\dist if it is missing (npm ci + npm run build).
  3. Checks that the port is free, then serves http://127.0.0.1:<Port>/ with uvicorn.
  Do not run scripts\load.ps1 while the app is running: it rebuilds the tables the app reads.

.PARAMETER Port
  Port to listen on (default 8000).
.PARAMETER Rebuild
  Rebuild the web app even if app\web\dist exists.
#>
param([int]$Port = 8000, [switch]$Rebuild)

. "$PSScriptRoot\_common.ps1"
Set-Location $script:RepoRoot
$py = Join-Path $script:RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw 'Python environment missing. Run scripts\bootstrap.ps1 first.' }

Write-Step 'Checking the database'
$status = (& "$PSScriptRoot\exa.ps1" status) -join "`n"
if ($status -notmatch 'database_ready') {
    Write-Host $status
    throw 'Exasol is not ready. Start it with: scripts\exa.ps1 start   (first time: scripts\exa.ps1 install local --auto-approve)'
}
$schema = if ($env:VOLTPROOF_SCHEMA) { $env:VOLTPROOF_SCHEMA } else { 'VOLTPROOF' }
$ErrorActionPreference = 'Continue'
$probe = & $py -c "from pipeline.db import connect; c = connect(schema='$schema'); print(c.execute('SELECT COUNT(*) FROM QUALITY_LOCATION').fetchval())" 2>&1
$ErrorActionPreference = 'Stop'
if ($LASTEXITCODE -ne 0) {
    throw "The analysis tables are missing. Build them first: scripts\get-data.ps1 then scripts\load.ps1`n$probe"
}
Write-Host "  analysed locations: $probe"

$dist = Join-Path $script:RepoRoot 'app\web\dist\index.html'
if ($Rebuild -or -not (Test-Path $dist)) {
    Write-Step 'Building the web app'
    Push-Location (Join-Path $script:RepoRoot 'app\web')
    try {
        $ErrorActionPreference = 'Continue'
        if (-not (Test-Path 'node_modules')) { npm.cmd ci --no-audit --no-fund 2>&1 | Select-Object -Last 2 }
        npm.cmd run build 2>&1 | Select-Object -Last 3
        if ($LASTEXITCODE -ne 0) { throw 'web build failed' }
    } finally { Pop-Location; $ErrorActionPreference = 'Stop' }
}

Write-Step "Checking that port $Port is free"
try {
    $l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    $l.Start(); $l.Stop()
} catch {
    throw "Port $Port is already in use. Stop the other process or run: scripts\start.ps1 -Port 8010"
}

Write-Host ''
Write-Host "  VoltProof is starting at  http://127.0.0.1:$Port/" -ForegroundColor Green
Write-Host '  (press Ctrl+C to stop)'
Write-Host ''
# uvicorn logs to stderr; Windows PowerShell 5.1 turns redirected native stderr into error records, which would
# stop the script (and the server) under 'Stop' when the output is captured to a file (clean-start test, 2026-10-12)
$ErrorActionPreference = 'Continue'
& $py -m uvicorn app.api.main:app --host 127.0.0.1 --port $Port
