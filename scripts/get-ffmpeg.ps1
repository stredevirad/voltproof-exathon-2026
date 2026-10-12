<#
.SYNOPSIS
  Fetches a pinned ffmpeg build into .tools\ffmpeg for the demo-video tooling only (pipeline\video.py).

.DESCRIPTION
  ffmpeg is NOT a runtime dependency of VoltProof and is not needed to build, run or test it. It is used only to
  merge the narration with the silent screen recording into the submission MP4.
  Source: BtbN/FFmpeg-Builds, release autobuild-2026-10-11-13-04, asset ffmpeg-n8.1.3-17-gc389840894-win64-gpl-8.1.zip,
  verified against that release's checksums.sha256 before unpacking. GPL build (it includes libx264); used
  locally as a tool and never redistributed (THIRD_PARTY_NOTICES.md).
#>
. "$PSScriptRoot\_common.ps1"
Set-Location $script:RepoRoot

$tag = 'autobuild-2026-10-11-13-04'
$zipName = 'ffmpeg-n8.1.3-17-gc389840894-win64-gpl-8.1.zip'
$base = "https://github.com/BtbN/FFmpeg-Builds/releases/download/$tag"
$dest = Join-Path $script:RepoRoot '.tools\ffmpeg'
$exe = Join-Path $dest 'ffmpeg-n8.1.3-17-gc389840894-win64-gpl-8.1\bin\ffmpeg.exe'
if (Test-Path $exe) { Write-Host "  ffmpeg already present ($exe)"; exit 0 }

$dl = Join-Path $env:VOLTPROOF_CACHE 'downloads'
New-Item -ItemType Directory -Force -Path $dl | Out-Null
$ProgressPreference = 'SilentlyContinue'
Write-Step "Fetching ffmpeg ($tag)"
$zip = Join-Path $dl $zipName
Invoke-WebRequest -Uri "$base/$zipName" -OutFile $zip -UseBasicParsing
$sums = (Invoke-WebRequest -Uri "$base/checksums.sha256" -UseBasicParsing).Content
if ($sums -is [byte[]]) { $sums = [Text.Encoding]::UTF8.GetString($sums) }
$expected = ($sums -split "`n" | Where-Object { $_ -match [regex]::Escape($zipName) } |
    ForEach-Object { ($_ -split '\s+')[0] } | Select-Object -First 1)
$actual = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
if (-not $expected -or $expected -ne $actual) {
    throw "Checksum mismatch for ${zipName}: expected '$expected', got '$actual'."
}
Write-Host "  SHA-256 verified: $actual"
Expand-Archive -Path $zip -DestinationPath $dest -Force
& $exe -hide_banner -version | Select-Object -First 1
