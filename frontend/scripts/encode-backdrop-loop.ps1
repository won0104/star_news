<#
  Re-encode the home backdrop loop.

      powershell -ExecutionPolicy Bypass -File scripts\encode-backdrop-loop.ps1 -Source <path-to.mp4>

  Writes public\assets\home\backdrop-loop.mp4 and .webm, overwriting what is there.
  The committed files were produced by exactly this recipe from a 1280x720 / 10fps /
  10s / H.264+AAC / 12.3MB render of public\assets\home\backdrop.png, and came out at
  350KB and 184KB. Nothing here needs running unless the clip itself changes.

  ffmpeg is not a project dependency and is not installed on every machine:
      winget install Gyan.FFmpeg      (then open a new terminal)

  Colour: the source render sits about a stop under backdrop.png, and the correction
  lives in CSS - see the .loop block in src/components/common/PhotoBackdrop.module.css.
  A different source means those two numbers have to be measured again, so keep the two
  files in step. Nothing in this script touches exposure.
#>

param(
  [Parameter(Mandatory = $true)]
  [string]$Source
)

$ErrorActionPreference = 'Stop'

# Run from anywhere; paths below are relative to frontend/.
Set-Location (Split-Path $PSScriptRoot -Parent)

$OutDir = 'public\assets\home'
$Name = 'backdrop-loop'

if (-not (Test-Path $Source)) { throw "Source not found: $Source" }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  throw 'ffmpeg is not on PATH. winget install Gyan.FFmpeg, then open a new terminal.'
}

# -an                   drop the audio track; a background loop plays muted and the
#                       source carried a 317kbps AAC stream nobody will ever hear
# -vf fps=8             resample to 8fps (source is 10fps, so 20% fewer frames)
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
Write-Host 'backdrop.png is already the still underneath, at higher resolution.'
