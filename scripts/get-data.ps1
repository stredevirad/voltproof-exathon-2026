<#
.SYNOPSIS
  Verifies (and optionally downloads) the ESMI raw files in data\raw against Harvard Dataverse checksums.

.DESCRIPTION
  Data: Prayas (Energy Group), ESMI minute-wise voltage data, doi:10.7910/DVN/CLLZZM (CC0 1.0;
  see docs\data\SOURCE_TERMS.md for Prayas's terms of use and attribution).

  Two ways to get the files:
    1. Browser: download from https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/CLLZZM
       into data\raw\ (keep file names; pick "Original File Format" for tabular files), then run this
       script to verify them.
    2. Script: put YOUR OWN Guestbook details in .env (DATAVERSE_GB_*; see .env.example) and run with
       -Download. Dataverse records one Guestbook response per downloaded file.

  Writes data\manifest.json (sizes, MD5, SHA-256; no personal details).

.PARAMETER Set
  meta  = location file + documentation PDF
  first = meta + one data file (2018 June-Aug), enough for a first end-to-end run
  up    = meta + every file covering Uttar Pradesh 2016-2019 (validation subset)
  all   = every file in the dataset

.EXAMPLE
  scripts\get-data.ps1                 # verify the 'first' set
  scripts\get-data.ps1 -Set up -Download
#>
param(
    [ValidateSet('meta', 'first', 'up', 'all')][string]$Set = 'first',
    [switch]$Download,
    [switch]$RefreshMetadata,
    [string]$Dest = ''
)

. "$PSScriptRoot\_common.ps1"
Set-Location $script:RepoRoot

$py = Join-Path $script:RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Python environment missing. Run scripts\bootstrap.ps1 first." }

$argsList = @('-m', 'pipeline.get_data', '--set', $Set)
if ($Download) { $argsList += '--download' }
if ($RefreshMetadata) { $argsList += '--refresh-metadata' }
if ($Dest) { $argsList += @('--dest', $Dest) }

Write-Step "Checking ESMI files ($Set) in $(if ($Dest) { $Dest } else { 'data\raw' })"
$ErrorActionPreference = 'Continue'
& $py @argsList
$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-Host "Some files are missing or failed verification (see above)." -ForegroundColor Yellow
}
exit $code
