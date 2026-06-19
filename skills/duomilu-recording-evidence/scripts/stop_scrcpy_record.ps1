param(
    [Parameter(Mandatory = $true)]
    [string]$PidFile,
    [int]$GraceSeconds = 3
)

$ErrorActionPreference = "Stop"

$pidPath = [System.IO.Path]::GetFullPath($PidFile)
if (-not (Test-Path -LiteralPath $pidPath)) {
    throw "Pid file not found: $pidPath"
}

$meta = Get-Content -Raw -LiteralPath $pidPath | ConvertFrom-Json
$proc = Get-Process -Id ([int]$meta.pid) -ErrorAction SilentlyContinue

if ($proc) {
    Close-ProcessMainWindow $proc $GraceSeconds
    $proc = Get-Process -Id ([int]$meta.pid) -ErrorAction SilentlyContinue
    if ($proc) {
        Stop-Process -Id ([int]$meta.pid) -Force
    }
}

$meta | Add-Member -NotePropertyName stopped_at -NotePropertyValue (Get-Date).ToString("o") -Force
$meta | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -LiteralPath $pidPath

[ordered]@{
    ok = $true
    pid = [int]$meta.pid
    output = $meta.output
    pid_file = $pidPath
} | ConvertTo-Json -Depth 4

function Close-ProcessMainWindow {
    param(
        [System.Diagnostics.Process]$Process,
        [int]$Seconds
    )

    if ($Process.MainWindowHandle -ne 0) {
        [void]$Process.CloseMainWindow()
        try {
            $Process.WaitForExit($Seconds * 1000)
        } catch {
        }
    }
}
