param(
  [Parameter(Mandatory = $true)]
  [string]$Path,
  [int]$Width = 0,
  [int]$Height = 0,
  [double]$Fps = 0,
  [double]$Duration = 0,
  [double]$DurationTolerance = 0.25
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Path)) {
  throw "Video not found: $Path"
}

$resolved = (Resolve-Path -LiteralPath $Path).Path
$raw = & ffprobe -v error `
  -show_entries 'format=duration,size,bit_rate' `
  -show_entries 'stream=index,codec_type,codec_name,width,height,r_frame_rate,bit_rate,sample_rate,channels' `
  -of json -- $resolved

if ($LASTEXITCODE -ne 0) {
  throw "ffprobe failed for: $resolved"
}

$probe = $raw | ConvertFrom-Json
$video = $probe.streams | Where-Object { $_.codec_type -eq 'video' } | Select-Object -First 1
$audio = $probe.streams | Where-Object { $_.codec_type -eq 'audio' } | Select-Object -First 1

if (-not $video) {
  throw 'No video stream found.'
}

$fpsValue = 0.0
if ($video.r_frame_rate -match '^([0-9.]+)/([0-9.]+)$') {
  $denominator = [double]$Matches[2]
  if ($denominator -ne 0) {
    $fpsValue = [double]$Matches[1] / $denominator
  }
}

$durationValue = [double]$probe.format.duration
$checks = [ordered]@{
  hasVideo = $null -ne $video
  hasAudio = $null -ne $audio
  width = if ($Width -gt 0) { [int]$video.width -eq $Width } else { $true }
  height = if ($Height -gt 0) { [int]$video.height -eq $Height } else { $true }
  fps = if ($Fps -gt 0) { [Math]::Abs($fpsValue - $Fps) -lt 0.01 } else { $true }
  duration = if ($Duration -gt 0) { [Math]::Abs($durationValue - $Duration) -le $DurationTolerance } else { $true }
}

$passed = -not ($checks.Values -contains $false)
$result = [ordered]@{
  passed = $passed
  path = $resolved
  durationSeconds = [Math]::Round($durationValue, 3)
  sizeBytes = [int64]$probe.format.size
  totalBitRate = [int64]$probe.format.bit_rate
  video = [ordered]@{
    codec = $video.codec_name
    width = [int]$video.width
    height = [int]$video.height
    fps = [Math]::Round($fpsValue, 3)
    bitRate = if ($video.bit_rate) { [int64]$video.bit_rate } else { $null }
  }
  audio = if ($audio) {
    [ordered]@{
      codec = $audio.codec_name
      sampleRate = [int]$audio.sample_rate
      channels = [int]$audio.channels
      bitRate = if ($audio.bit_rate) { [int64]$audio.bit_rate } else { $null }
    }
  } else { $null }
  checks = $checks
}

$result | ConvertTo-Json -Depth 6
if (-not $passed) { exit 1 }
