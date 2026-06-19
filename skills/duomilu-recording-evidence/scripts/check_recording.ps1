param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [switch]$ExtractFrame,
    [string]$FrameOutput,
    [int64]$MinBytes = 102400
)

$ErrorActionPreference = "Stop"

$inputPath = [System.IO.Path]::GetFullPath($Path)
if (-not (Test-Path -LiteralPath $inputPath)) {
    throw "Recording not found: $inputPath"
}

$item = Get-Item -LiteralPath $inputPath
$result = [ordered]@{
    ok = $true
    input = $inputPath
    size_bytes = $item.Length
    min_bytes = $MinBytes
    size_ok = ($item.Length -ge $MinBytes)
    duration_seconds = $null
    video_streams = $null
    audio_streams = $null
    frame_output = $null
    tools = [ordered]@{
        ffprobe = $false
        ffmpeg = $false
    }
    warnings = @()
}

if (-not $result.size_ok) {
    $result.ok = $false
    $result.warnings += "Recording is smaller than expected."
}

$ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
if ($ffprobe) {
    $result.tools.ffprobe = $true
    $json = & $ffprobe.Source -v error -show_entries "format=duration,size:stream=codec_type" -of json $inputPath
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($json)) {
        $probe = $json | ConvertFrom-Json
        if ($probe.format.duration) {
            $result.duration_seconds = [double]$probe.format.duration
        }
        $streams = @($probe.streams)
        $result.video_streams = @($streams | Where-Object { $_.codec_type -eq "video" }).Count
        $result.audio_streams = @($streams | Where-Object { $_.codec_type -eq "audio" }).Count
        if ($result.video_streams -lt 1) {
            $result.ok = $false
            $result.warnings += "No video stream found."
        }
    }
} else {
    $result.warnings += "ffprobe not found; duration and stream checks skipped."
}

if ($ExtractFrame) {
    $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($ffmpeg) {
        $result.tools.ffmpeg = $true
        if ([string]::IsNullOrWhiteSpace($FrameOutput)) {
            $FrameOutput = [System.IO.Path]::ChangeExtension($inputPath, ".frame.png")
        }
        $framePath = [System.IO.Path]::GetFullPath($FrameOutput)
        $frameDir = [System.IO.Path]::GetDirectoryName($framePath)
        if (-not [string]::IsNullOrWhiteSpace($frameDir)) {
            New-Item -ItemType Directory -Force -Path $frameDir | Out-Null
        }
        & $ffmpeg.Source -y -i $inputPath -frames:v 1 $framePath | Out-Null
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $framePath)) {
            $result.frame_output = $framePath
        } else {
            $result.ok = $false
            $result.warnings += "Frame extraction failed."
        }
    } else {
        $result.warnings += "ffmpeg not found; frame extraction skipped."
    }
}

$result | ConvertTo-Json -Depth 5
