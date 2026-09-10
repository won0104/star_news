<#
  Re-encode a background clip for the web.

      powershell -ExecutionPolicy Bypass -File scripts\encode-clip.ps1 `
        -Source <path-to.mp4> -Name backdrop-loop -OutDir public\assets\home

  Writes <OutDir>\<Name>.mp4 and .webm, overwriting what is there. Nothing here needs
  running unless a clip itself changes.

  The two clips in the project:

    home    -Name backdrop-loop -OutDir public\assets\home
            Produced by exactly this recipe from a 1280x720 / 10fps / 10s / H.264+AAC /
            12.3MB render of public\assets\home\backdrop.png, and came out at 350KB and
            184KB. Referenced as `backdrop.loop` in src\data\home.js.

    trend   -Name nightfall -OutDir public\assets\trend
            NOT yet run: the committed nightfall.mp4 is the render as delivered, 2.4MB
            with a 10s H.264 stream and an AAC track the player mutes. This recipe drops
            the audio and resamples the frame rate, so expect a few hundred KB. Referenced
            as `nightfall` in src\data\trend.js. Because files in public\ carry no content
            hash, encode to a NEW name (nightfall-v2) and change the path in that file,
            or a CDN will keep handing out the old bytes.

  ffmpeg is not a project dependency and is not installed on every machine:
      winget install Gyan.FFmpeg      (then open a new terminal)

  Colour: neither clip's exposure is touched here. The home clip sits about a stop under
  backdrop.png and the correction lives in CSS - see the .loop block in
  src\components\common\PhotoBackdrop.module.css. A different source means those numbers
  have to be measured again, so keep the two files in step. The trend clip needs no such
  correction; what it needs is noted in TrendStage.module.css, and re-encoding will not
  change it (the clip simply ends darker than the still it hands back to).
#>

param(
  [Parameter(Mandatory = $true)]
  [string]$Source,

  [Parameter(Mandatory = $true)]
  [string]$Name,

  [Parameter(Mandatory = $true)]
  [string]$OutDir
)

$ErrorActionPreference = 'Stop'

# Run from anywhere; paths below are relative to frontend/.
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path $Source)) { throw "Source not found: $Source" }
if (-not (Test-Path $OutDir)) { throw "Output directory not found: $OutDir" }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  throw 'ffmpeg is not on PATH. winget install Gyan.FFmpeg, then open a new terminal.'
}

# -an                   drop the audio track; a background clip plays muted and both
#                       sources carried an AAC stream nobody will ever hear
# -vf fps=8             resample to 8fps (both sources are 10fps, so 20% fewer frames)
# -crf 26 / 34          quality dial. Higher is smaller and mushier; 26-30 for H.264,
#                       32-36 for VP9, which lands ~30-40% smaller at equal quality
# -pix_fmt yuv420p      required for Safari and anything older
# -movflags +faststart  moov box to the front, so playback starts before the whole
#                       file has arrived
Write-Host '[1/2] mp4 (H.264) ...' -ForegroundColor Cyan
ffmpeg -y -i $Source -an -vf 'fps=8' -c:v libx264 -profile:v high -pix_fmt yuv420p `
  -crf 26 -preset slow -movflags +faststart "$OutDir\$Name.mp4"

Write-Host '[2/2] webm (VP9) ...' -ForegroundColor Cyan
ffmpeg -y -i $Source -an -vf 'fps=8' -c:v libvpx-vp9 -crf 34 -b:v 0 -row-mt 1 `
  -pix_fmt yuv420p "$OutDir\$Name.webm"

Write-Host ''
Write-Host 'Result:' -ForegroundColor Green
Get-ChildItem "$OutDir\$Name.*" | ForEach-Object {
  '{0,-24} {1,7:N0} KB' -f $_.Name, ($_.Length / 1KB)
}
Write-Host ''
Write-Host 'Over ~1MB? Raise -crf and run again. There is no poster file to make:'
Write-Host 'both screens paint a still underneath and fade the clip in over it.'
