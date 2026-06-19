param(
    [string]$Serial,
    [Parameter(Mandatory = $true)]
    [string]$Output,
    [int]$TimeLimitSeconds = 10,
    [string]$RemotePath = "/sdcard/duomilu-recording-evidence.mp4"
)

$ErrorActionPreference = "Stop"

$adb = (Get-Command adb -ErrorAction SilentlyContinue)
if (-not $adb) {
    throw "adb was not found in PATH."
}

if ($TimeLimitSeconds -lt 1) {
    throw "TimeLimitSeconds must be greater than 0 for adb screenrecord."
}

$outPath = [System.IO.Path]::GetFullPath($Output)
$outDir = [System.IO.Path]::GetDirectoryName($outPath)
if (-not [string]::IsNullOrWhiteSpace($outDir)) {
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
}

$adbArgs = @()
if (-not [string]::IsNullOrWhiteSpace($Serial)) {
    $adbArgs += @("-s", $Serial)
}

& $adb.Source @adbArgs shell rm -f $RemotePath | Out-Null
& $adb.Source @adbArgs shell screenrecord --time-limit $TimeLimitSeconds $RemotePath
if ($LASTEXITCODE -ne 0) {
    throw "adb screenrecord failed."
}

& $adb.Source @adbArgs pull $RemotePath $outPath | Out-Null
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $outPath)) {
    throw "adb pull recording failed."
}

& $adb.Source @adbArgs shell rm -f $RemotePath | Out-Null

$item = Get-Item -LiteralPath $outPath
[ordered]@{
    ok = $true
    serial = $Serial
    output = $outPath
    size_bytes = $item.Length
    note = "ADB screenrecord fallback is video-only evidence."
} | ConvertTo-Json -Depth 4
