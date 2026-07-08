param(
    [string]$OutputPath,
    [int]$ProcessId = 0,
    [string]$TitleRegex = "",
    [switch]$Json
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $OutputPath = Join-Path (Get-Location) "ue_window_$stamp.png"
}

$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDir = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($outputDir)) {
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
}

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;

public static class UeWindowCaptureNative
{
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool IsIconic(IntPtr hWnd);
}
'@

function New-Result {
    param(
        [bool]$Success,
        [string]$Message,
        [object]$Process,
        [object]$Rect,
        [string]$Warning = ""
    )

    $width = 0
    $height = 0
    if ($null -ne $Rect) {
        $width = $Rect.Right - $Rect.Left
        $height = $Rect.Bottom - $Rect.Top
    }

    [pscustomobject]@{
        success = $Success
        message = $Message
        outputPath = $OutputPath
        metadataPath = [System.IO.Path]::ChangeExtension($OutputPath, ".json")
        processId = if ($Process) { $Process.Id } else { $null }
        processName = if ($Process) { $Process.ProcessName } else { $null }
        windowTitle = if ($Process) { $Process.MainWindowTitle } else { $null }
        windowHandle = if ($Process) { [string]$Process.MainWindowHandle } else { $null }
        rect = if ($null -ne $Rect) {
            [pscustomobject]@{
                left = $Rect.Left
                top = $Rect.Top
                right = $Rect.Right
                bottom = $Rect.Bottom
            }
        } else { $null }
        width = $width
        height = $height
        isVisible = if ($Process) { [UeWindowCaptureNative]::IsWindowVisible([intptr]$Process.MainWindowHandle) } else { $false }
        isIconic = if ($Process) { [UeWindowCaptureNative]::IsIconic([intptr]$Process.MainWindowHandle) } else { $false }
        warning = $Warning
        capturedAt = (Get-Date).ToString("o")
    }
}

$candidates = Get-Process UnrealEditor -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 }

if ($ProcessId -gt 0) {
    $candidates = $candidates | Where-Object { $_.Id -eq $ProcessId }
}

if (-not [string]::IsNullOrWhiteSpace($TitleRegex)) {
    $candidates = $candidates | Where-Object { $_.MainWindowTitle -match $TitleRegex }
}

$target = $candidates | Sort-Object StartTime -Descending | Select-Object -First 1
if (-not $target) {
    $result = New-Result -Success $false -Message "No matching UnrealEditor window found." -Process $null -Rect $null
    $result | ConvertTo-Json -Depth 8 | Set-Content -Path ([System.IO.Path]::ChangeExtension($OutputPath, ".json")) -Encoding UTF8
    if ($Json) { $result | ConvertTo-Json -Depth 8 }
    exit 2
}

$hwnd = [intptr]$target.MainWindowHandle
$rect = New-Object UeWindowCaptureNative+RECT
if (-not [UeWindowCaptureNative]::GetWindowRect($hwnd, [ref]$rect)) {
    $result = New-Result -Success $false -Message "GetWindowRect failed." -Process $target -Rect $null
    $result | ConvertTo-Json -Depth 8 | Set-Content -Path ([System.IO.Path]::ChangeExtension($OutputPath, ".json")) -Encoding UTF8
    if ($Json) { $result | ConvertTo-Json -Depth 8 }
    exit 3
}

$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
$warning = ""

if (-not [UeWindowCaptureNative]::IsWindowVisible($hwnd)) {
    $warning = "Target window is not visible."
}
if ([UeWindowCaptureNative]::IsIconic($hwnd)) {
    $warning = "Target window is minimized; captured pixels are unreliable."
}
if ($width -le 0 -or $height -le 0) {
    $result = New-Result -Success $false -Message "Invalid window rectangle." -Process $target -Rect $rect -Warning $warning
    $result | ConvertTo-Json -Depth 8 | Set-Content -Path ([System.IO.Path]::ChangeExtension($OutputPath, ".json")) -Encoding UTF8
    if ($Json) { $result | ConvertTo-Json -Depth 8 }
    exit 4
}

$bitmap = New-Object System.Drawing.Bitmap $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
    $bitmap.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
}
finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}

$result = New-Result -Success $true -Message "Captured UnrealEditor window." -Process $target -Rect $rect -Warning $warning
$result | ConvertTo-Json -Depth 8 | Set-Content -Path ([System.IO.Path]::ChangeExtension($OutputPath, ".json")) -Encoding UTF8
if ($Json) {
    $result | ConvertTo-Json -Depth 8
} else {
    Write-Output $OutputPath
}
