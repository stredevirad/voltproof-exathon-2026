# Shared setup for VoltProof scripts. Dot-source it: . "$PSScriptRoot\_common.ps1"
# - resolves the repo root
# - loads .env (KEY=VALUE lines) into the process environment without printing values
# - points every tool cache at the repo's gitignored .cache folder on the same drive as the repo
# - makes the project-local tools (.tools\) and Podman visible on PATH

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$script:RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Import-DotEnv {
    param([string]$Path = (Join-Path $script:RepoRoot '.env'))
    if (-not (Test-Path $Path)) { return }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $t = $line.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        $idx = $t.IndexOf('=')
        if ($idx -lt 1) { continue }
        $key = $t.Substring(0, $idx).Trim()
        $val = $t.Substring($idx + 1).Trim().Trim('"')
        # .env never overrides a value the caller set explicitly
        if (-not [Environment]::GetEnvironmentVariable($key, 'Process')) {
            [Environment]::SetEnvironmentVariable($key, $val, 'Process')
        }
    }
}

Import-DotEnv

$cache = if ($env:VOLTPROOF_CACHE) { $env:VOLTPROOF_CACHE } else { Join-Path $script:RepoRoot '.cache' }
New-Item -ItemType Directory -Force -Path $cache | Out-Null
$env:VOLTPROOF_CACHE        = $cache
$env:UV_CACHE_DIR           = Join-Path $cache 'uv'
$env:UV_PYTHON_INSTALL_DIR  = Join-Path $cache 'uv-python'
$env:UV_PYTHON_PREFERENCE   = 'only-managed'
$env:PIP_CACHE_DIR          = Join-Path $cache 'pip'
$env:npm_config_cache       = Join-Path $cache 'npm'
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $cache 'ms-playwright'
$env:HYPOTHESIS_STORAGE_DIRECTORY = Join-Path $cache 'hypothesis'
$env:VOLTPROOF_TMP          = Join-Path $cache 'tmp'
$env:PYTHONUNBUFFERED       = '1'   # stream Python progress into logs instead of buffering it
$env:PYTHONIOENCODING       = 'utf-8'
New-Item -ItemType Directory -Force -Path $env:VOLTPROOF_TMP | Out-Null

# Default: <drive of the repository>\ExasolDeployments\voltproof (override with EXASOL_DEPLOYMENT_DIR in .env)
if (-not $env:EXASOL_DEPLOYMENT_DIR) {
    $env:EXASOL_DEPLOYMENT_DIR = Join-Path (Split-Path $script:RepoRoot -Qualifier) 'ExasolDeployments\voltproof'
}

$script:ExasolExe = Join-Path $script:RepoRoot '.tools\exasol\exasol.exe'
$script:GitleaksExe = Join-Path $script:RepoRoot '.tools\gitleaks\gitleaks.exe'

# Podman installed by winget may not be on PATH in terminals opened before the install.
$podmanDir = 'C:\Program Files\RedHat\Podman'
if ((Test-Path (Join-Path $podmanDir 'podman.exe')) -and ($env:PATH -notlike "*$podmanDir*")) {
    $env:PATH = "$podmanDir;$env:PATH"
}

function Write-Step([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

function Get-FreeGB([string]$drive) { [math]::Round((Get-PSDrive $drive).Free / 1GB, 2) }
