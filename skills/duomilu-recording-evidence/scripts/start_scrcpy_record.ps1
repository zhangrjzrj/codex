param(
    [string]$Serial,
    [Parameter(Mandatory = $true)]
    [string]$Output,
    [string]$PidFile,
    [int]$TimeLimitSeconds = 0,
    [switch]$NoPlayback = $true
)

$ErrorActionPreference = "Stop"

$scrcpy = (Get-Command scrcpy -ErrorAction SilentlyContinue)
if (-not $scrcpy) {
    throw "scrcpy was not found in PATH."
}

$outPath = [System.IO.Path]::GetFullPath($Output)
$outDir = [System.IO.Path]::GetDirectoryName($outPath)
if (-not [string]::IsNullOrWhiteSpace($outDir)) {
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
}

if ([string]::IsNullOrWhiteSpace($PidFile)) {
    $PidFile = [System.IO.Path]::ChangeExtension($outPath, ".scrcpy-pid.json")
}
$pidPath = [System.IO.Path]::GetFullPath($PidFile)
$pidDir = [System.IO.Path]::GetDirectoryName($pidPath)
if (-not [string]::IsNullOrWhiteSpace($pidDir)) {
    New-Item -ItemType Directory -Force -Path $pidDir | Out-Null
}

$argsList = @()
if (-not [string]::IsNullOrWhiteSpace($Serial)) {
    $argsList += @("-s", $Serial)
}
if ($NoPlayback) {
    $argsList += "--no-playback"
}
$argsList += @("--record", $outPath)
if ($TimeLimitSeconds -gt 0) {
    $argsList += @("--time-limit", $TimeLimitSeconds.ToString())
}

$proc = Start-Process -FilePath $scrcpy.Source -ArgumentList $argsList -PassThru -WindowStyle Hidden

$meta = [ordered]@{
    pid = $proc.Id
    serial = $Serial
    output = $outPath
    started_at = (Get-Date).ToString("o")
    command = $scrcpy.Source
    arguments = $argsList
}
$meta | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -Path $pidPath

[ordered]@{
    ok = $true
    pid = $proc.Id
    pid_file = $pidPath
    output = $outPath
} | ConvertTo-Json -Depth 4
