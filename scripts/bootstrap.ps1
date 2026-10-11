<#
.SYNOPSIS
  One-time setup: checks prerequisites, creates the Python environment and fetches pinned tools.

.DESCRIPTION
  Everything is installed inside the repository (gitignored .cache\ and .tools\ folders); nothing is
  installed system-wide by this script. It does NOT install Podman or start the database. See
  docs\SETUP_WINDOWS.md for those steps.

  Steps
    1. Check prerequisites: git, uv, Node.js (>= 20), Podman (warn only), free disk space.
    2. Install CPython 3.12 managed by uv into .cache\uv-python (no shims, no registry entries).
    3. Create .venv and install the locked Python dependencies (uv sync).
    4. Download the Exasol Launcher v2.3.0 and gitleaks v8.30.1 from their GitHub releases, verify the
       published SHA-256 checksums, and unpack them into .tools\.
#>
param([switch]$SkipTools)

. "$PSScriptRoot\_common.ps1"
Set-Location $script:RepoRoot

$Pinned = @(
    @{ Name = 'exasol'; Version = '2.3.0'; Zip = 'exasol-personal_Windows_x86_64.zip'
       Url = 'https://github.com/exasol/exasol-personal/releases/download/v2.3.0/exasol-personal_Windows_x86_64.zip'
       Sums = 'https://github.com/exasol/exasol-personal/releases/download/v2.3.0/exasol-personal_2.3.0_checksums.txt'
       Exe = 'exasol.exe' },
    @{ Name = 'gitleaks'; Version = '8.30.1'; Zip = 'gitleaks_8.30.1_windows_x64.zip'
       Url = 'https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_windows_x64.zip'
       Sums = 'https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_checksums.txt'
       Exe = 'gitleaks.exe' }
)

function Test-Tool([string]$name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }

Write-Step 'Checking prerequisites'
$missing = @()
foreach ($t in 'git', 'uv', 'node', 'npm') { if (-not (Test-Tool $t)) { $missing += $t } }
if ($missing) {
    throw ("Missing prerequisites: {0}. Install them (see docs\SETUP_WINDOWS.md) and re-run." -f ($missing -join ', '))
}
$nodeMajor = [int]((node --version).TrimStart('v').Split('.')[0])
if ($nodeMajor -lt 20) { throw "Node.js 20 or newer is required (found $(node --version))." }
if (-not (Test-Path 'C:\Program Files\RedHat\Podman\podman.exe') -and -not (Test-Tool 'podman')) {
    Write-Warning 'Podman not found. The database needs it: winget install -e --id RedHat.Podman'
}
Write-Host ("  git {0} | uv {1} | node {2}" -f (git --version).Split(' ')[2], (uv --version).Split(' ')[1], (node --version))
Write-Host ("  free space: C: {0} GB, D: {1} GB" -f (Get-FreeGB 'C'), (Get-FreeGB 'D'))
if ((Get-FreeGB 'C') -lt 10) { Write-Warning 'Less than 10 GB free on C:. The Podman machine and image need about 3 GB there.' }

Write-Step 'Installing Python 3.12 (uv-managed, inside .cache)'
$ErrorActionPreference = 'Continue'
uv python install 3.12 --no-bin --no-registry 2>&1 | ForEach-Object { "  $_" }
if ($LASTEXITCODE -ne 0) { throw 'uv python install failed' }

Write-Step 'Creating .venv and installing Python dependencies (uv sync)'
uv sync --python 3.12 2>&1 | ForEach-Object { "  $_" }
if ($LASTEXITCODE -ne 0) { throw 'uv sync failed' }
$ErrorActionPreference = 'Stop'

if (-not $SkipTools) {
    $dl = Join-Path $env:VOLTPROOF_CACHE 'downloads'
    New-Item -ItemType Directory -Force -Path $dl | Out-Null
    $ProgressPreference = 'SilentlyContinue'
    foreach ($p in $Pinned) {
        $dest = Join-Path $script:RepoRoot ".tools\$($p.Name)"
        $exe = Join-Path $dest $p.Exe
        if (Test-Path $exe) {
            Write-Host "  $($p.Name) already present ($exe)"
            continue
        }
        Write-Step "Fetching $($p.Name) v$($p.Version)"
        $zip = Join-Path $dl $p.Zip
        Invoke-WebRequest -Uri $p.Url -OutFile $zip -UseBasicParsing
        $sums = (Invoke-WebRequest -Uri $p.Sums -UseBasicParsing).Content
        if ($sums -is [byte[]]) { $sums = [Text.Encoding]::UTF8.GetString($sums) }
        $expected = ($sums -split "`n" | Where-Object { $_ -match [regex]::Escape($p.Zip) } |
            ForEach-Object { ($_ -split '\s+')[0] } | Select-Object -First 1)
        $actual = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
        if (-not $expected -or $expected -ne $actual) {
            Remove-Item $zip -Force
            throw "Checksum mismatch for $($p.Zip): expected '$expected', got '$actual'."
        }
        Write-Host "  SHA-256 verified: $actual"
        Expand-Archive -Path $zip -DestinationPath $dest -Force
    }
}

Write-Step 'Installing Playwright Chromium (PDF reports and browser tests) into .cache\ms-playwright'
$ErrorActionPreference = 'Continue'
& (Join-Path $script:RepoRoot '.venv\Scripts\python.exe') -m playwright install chromium 2>&1 |
    Select-Object -Last 2 | ForEach-Object { "  $_" }
if ($LASTEXITCODE -ne 0) { throw 'playwright install chromium failed' }
$ErrorActionPreference = 'Stop'

Write-Step 'Building the web app (app\web -> app\web\dist)'
$web = Join-Path $script:RepoRoot 'app\web'
if (Test-Path (Join-Path $web 'package.json')) {
    Push-Location $web
    try {
        $ErrorActionPreference = 'Continue'
        npm.cmd ci --no-audit --no-fund 2>&1 | Select-Object -Last 2 | ForEach-Object { "  $_" }
        if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
        npm.cmd run build 2>&1 | Select-Object -Last 3 | ForEach-Object { "  $_" }
        if ($LASTEXITCODE -ne 0) { throw 'npm run build failed' }
    } finally { Pop-Location; $ErrorActionPreference = 'Stop' }
}

Write-Step 'Bootstrap complete'
Write-Host '  Next: start the database      -> scripts\exa.ps1 install local --auto-approve   (first time)'
Write-Host '                                   scripts\exa.ps1 start                          (afterwards)'
Write-Host '        get and verify the data -> scripts\get-data.ps1'
