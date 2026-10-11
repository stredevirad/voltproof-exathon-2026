<#
.SYNOPSIS
  Runs the Exasol Launcher against VoltProof's deployment directory.

.DESCRIPTION
  Every launcher call in this project goes through this wrapper so that the deployment directory is
  always explicit. (Without --deployment-dir the launcher silently uses
  ~\.exasol\personal\deployments\default.)

  Destructive commands are refused here on purpose: with no terminal attached, `exasol destroy` and
  `exasol remove` proceed WITHOUT asking. Run them yourself, directly, if you really need them.

.EXAMPLE
  scripts\exa.ps1 status
  scripts\exa.ps1 info
  scripts\exa.ps1 connect -c "SELECT 1"
  scripts\exa.ps1 install local
#>
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$LauncherArgs)

. "$PSScriptRoot\_common.ps1"

if (-not (Test-Path $script:ExasolExe)) {
    throw "Exasol Launcher not found at $script:ExasolExe. Run scripts\bootstrap.ps1 first."
}
if (-not $LauncherArgs -or $LauncherArgs.Count -eq 0) { $LauncherArgs = @('status') }

$blocked = @('destroy', 'remove')
foreach ($a in $LauncherArgs) {
    if ($blocked -contains $a.ToLowerInvariant()) {
        throw "Refusing '$a': it deletes the deployment without confirmation when run from a script. Run '$script:ExasolExe $a --deployment-dir $env:EXASOL_DEPLOYMENT_DIR' yourself if you are sure."
    }
    if ($a -match '^(--deployment|-d|--deployment-dir)$') {
        throw "Do not pass $a; this wrapper sets --deployment-dir from EXASOL_DEPLOYMENT_DIR."
    }
}

$parent = Split-Path $env:EXASOL_DEPLOYMENT_DIR -Parent
if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }

# The launcher accepts --deployment-dir after the subcommand path; place it after the first token
# (e.g. "install local --deployment-dir X", "connect --deployment-dir X -c ...").
$sub = @($LauncherArgs[0])
$rest = @()
if ($LauncherArgs.Count -gt 1) { $rest = $LauncherArgs[1..($LauncherArgs.Count - 1)] }
if ($sub[0] -in @('install', 'init', 'slc', 'config', 'diag', 'cache') -and $rest.Count -gt 0 -and -not $rest[0].StartsWith('-')) {
    $sub += $rest[0]
    $rest = if ($rest.Count -gt 1) { $rest[1..($rest.Count - 1)] } else { @() }
}

$argv = @($sub) + @('--deployment-dir', $env:EXASOL_DEPLOYMENT_DIR) + @($rest)
if ($env:VOLTPROOF_DEBUG) { Write-Host ("exasol " + ($argv -join ' | ')) }

# Run from the cache's tmp folder: Podman's ssh writes a file literally named "NUL" into the current
# directory on Windows, which must never land in the repository.
Push-Location $env:VOLTPROOF_TMP
try {
    # Windows PowerShell 5.1 turns native stderr lines into errors; with 'Stop' the first progress line
    # would abort the script. Let the launcher write freely and rely on its exit code instead.
    $ErrorActionPreference = 'Continue'
    & $script:ExasolExe @argv 2>&1 | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" }
    }
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $code
