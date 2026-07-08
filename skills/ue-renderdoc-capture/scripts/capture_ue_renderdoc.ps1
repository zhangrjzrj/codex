param(
    [int]$ProcessId = 0,
    [string]$ProjectRoot = "",
    [string]$Command = "renderdoc.CaptureFrame",
    [string]$McpUrl = "http://127.0.0.1:17881/mcp",
    [ValidateSet("auto", "mcp", "ui")]
    [string]$TriggerMode = "auto",
    [int]$TimeoutSeconds = 90,
    [switch]$AllowWithoutAttachRenderDoc,
    [switch]$LaunchRenderDocUi
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms

$nativeSource = @"
using System;
using System.Runtime.InteropServices;

public static class UeRenderDocWin32 {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll")] public static extern void mouse_event(int dwFlags, int dx, int dy, int dwData, UIntPtr dwExtraInfo);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, System.Text.StringBuilder lpClassName, int nMaxCount);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);

    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }
}
"@

try {
    Add-Type $nativeSource -ErrorAction Stop
} catch {
    if ($_.Exception.Message -notmatch "already exists") {
        throw
    }
}

function ConvertTo-JsonResult {
    param([hashtable]$Result, [int]$ExitCode)
    $Result | ConvertTo-Json -Depth 12
    exit $ExitCode
}

function Get-EditorProcess {
    param([int]$PidValue)
    if ($PidValue -gt 0) {
        return Get-Process -Id $PidValue -ErrorAction Stop
    }
    $editors = @(Get-Process -Name "UnrealEditor" -ErrorAction SilentlyContinue)
    if ($editors.Count -eq 0) {
        throw "No UnrealEditor.exe process found."
    }
    if ($editors.Count -gt 1) {
        throw "Multiple UnrealEditor.exe processes found. Pass -ProcessId explicitly."
    }
    return $editors[0]
}

function Get-CommandLine {
    param([int]$PidValue)
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$PidValue" -ErrorAction Stop
    return [string]$proc.CommandLine
}

function Get-TopLevelWindows {
    $windows = New-Object System.Collections.Generic.List[object]
    $callback = [UeRenderDocWin32+EnumWindowsProc]{
        param([IntPtr]$hWnd, [IntPtr]$lParam)
        $pidRef = [uint32]0
        [UeRenderDocWin32]::GetWindowThreadProcessId($hWnd, [ref]$pidRef) | Out-Null
        $classBuilder = New-Object System.Text.StringBuilder 256
        [UeRenderDocWin32]::GetClassName($hWnd, $classBuilder, $classBuilder.Capacity) | Out-Null
        $windows.Add([pscustomobject]@{
            Handle = $hWnd
            ProcessId = [int]$pidRef
            ClassName = $classBuilder.ToString()
            Visible = [UeRenderDocWin32]::IsWindowVisible($hWnd)
            Iconic = [UeRenderDocWin32]::IsIconic($hWnd)
        })
        return $true
    }
    [UeRenderDocWin32]::EnumWindows($callback, [IntPtr]::Zero) | Out-Null
    return $windows
}

function Get-UnrealWindowHandle {
    param([int]$PidValue)
    $matches = @(Get-TopLevelWindows | Where-Object {
        $_.ProcessId -eq $PidValue -and
        $_.ClassName -eq "UnrealWindow" -and
        $_.Visible -and
        -not $_.Iconic
    })
    if ($matches.Count -gt 0) {
        return $matches[0].Handle
    }
    return [IntPtr]::Zero
}

function Minimize-ExistingRenderDocWindows {
    $renderDocProcesses = @(Get-Process -Name "qrenderdoc","renderdocui" -ErrorAction SilentlyContinue)
    foreach ($proc in $renderDocProcesses) {
        $windows = @(Get-TopLevelWindows | Where-Object { $_.ProcessId -eq $proc.Id -and $_.Visible -and -not $_.Iconic })
        foreach ($window in $windows) {
            [UeRenderDocWin32]::ShowWindow($window.Handle, 6) | Out-Null
        }
    }
}

function Infer-ProjectRoot {
    param([string]$CommandLine)
    if ($CommandLine -match "([A-Za-z]:\\[^`" ]+\.uproject)") {
        return Split-Path -Parent $Matches[1]
    }
    if ($CommandLine -match "([A-Za-z]:\\.*?\.uproject)") {
        return Split-Path -Parent $Matches[1]
    }
    return ""
}

function Get-LatestCapture {
    param([string[]]$Roots, [datetime]$Since)
    $items = @()
    foreach ($root in $Roots) {
        if ([string]::IsNullOrWhiteSpace($root) -or -not (Test-Path $root)) {
            continue
        }
        $items += Get-ChildItem -LiteralPath $root -Recurse -Filter "*.rdc" -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -ge $Since -and $_.Length -gt 0 }
    }
    return $items | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

function Invoke-McpJsonRpc {
    param([string]$Url, [hashtable]$Request)
    $body = $Request | ConvertTo-Json -Depth 20
    return Invoke-RestMethod -Uri $Url -Method Post -ContentType "application/json" -Body $body -TimeoutSec 30
}

function Invoke-McpRenderDocCapture {
    param([string]$Url, [bool]$Launch)

    $listResponse = Invoke-McpJsonRpc -Url $Url -Request @{
        jsonrpc = "2.0"
        id = 101
        method = "tools/list"
        params = @{}
    }

    $hasTool = $false
    foreach ($tool in @($listResponse.result.tools)) {
        if ($tool.name -eq "artclaw_renderdoc_capture_frame") {
            $hasTool = $true
            break
        }
    }
    if (-not $hasTool) {
        throw "ArtClaw MCP does not expose artclaw_renderdoc_capture_frame."
    }

    $callResponse = Invoke-McpJsonRpc -Url $Url -Request @{
        jsonrpc = "2.0"
        id = 102
        method = "tools/call"
        params = @{
            name = "artclaw_renderdoc_capture_frame"
            arguments = @{
                launch = $Launch
            }
        }
    }

    $structured = $callResponse.result.structuredContent
    if ($callResponse.result.isError -or ($structured -and $structured.success -eq $false)) {
        $message = if ($structured -and $structured.message) { $structured.message } else { ($callResponse | ConvertTo-Json -Depth 10) }
        throw "ArtClaw MCP renderdoc capture failed: $message"
    }

    return $callResponse
}

function Invoke-UiRenderDocCapture {
    param([System.Diagnostics.Process]$EditorProcess)

    Minimize-ExistingRenderDocWindows
    Start-Sleep -Milliseconds 300

    $ueWindowHandle = Get-UnrealWindowHandle -PidValue $EditorProcess.Id
    if ($ueWindowHandle -eq [IntPtr]::Zero) {
        if ($EditorProcess.MainWindowHandle -eq 0) {
            throw "UnrealEditor has no visible UnrealWindow handle."
        }
        $ueWindowHandle = $EditorProcess.MainWindowHandle
    }

    [UeRenderDocWin32]::ShowWindow($ueWindowHandle, 9) | Out-Null
    Start-Sleep -Milliseconds 250
    [UeRenderDocWin32]::SetForegroundWindow($ueWindowHandle) | Out-Null
    Start-Sleep -Milliseconds 350

    $rect = New-Object UeRenderDocWin32+RECT
    if (-not [UeRenderDocWin32]::GetWindowRect($ueWindowHandle, [ref]$rect)) {
        throw "Failed to read UnrealEditor window rectangle."
    }

    $cmdX = [Math]::Max($rect.Left + 360, $rect.Left + [int](($rect.Right - $rect.Left) * 0.28))
    $cmdY = $rect.Bottom - 52
    [UeRenderDocWin32]::SetCursorPos($cmdX, $cmdY) | Out-Null
    Start-Sleep -Milliseconds 100
    [UeRenderDocWin32]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 50
    [UeRenderDocWin32]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 200

    Set-Clipboard -Value $Command
    [System.Windows.Forms.SendKeys]::SendWait("^a")
    Start-Sleep -Milliseconds 80
    [System.Windows.Forms.SendKeys]::SendWait("^v")
    Start-Sleep -Milliseconds 80
    [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")

    return $ueWindowHandle
}

function Get-LogEvidence {
    param([string]$Root)
    $lines = @()
    if ($Root) {
        $logDir = Join-Path $Root "Saved\Logs"
        if (Test-Path $logDir) {
            $latestLog = Get-ChildItem -LiteralPath $logDir -Filter "*.log" -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTime -Descending |
                Select-Object -First 1
            if ($latestLog) {
                $lines = @(Select-String -LiteralPath $latestLog.FullName -Pattern "renderdoc\.CaptureFrame|Capture frame and launch renderdoc|RenderDocPlugin|ArtClaw.*RenderDoc" -ErrorAction SilentlyContinue |
                    Select-Object -Last 30 |
                    ForEach-Object { $_.Line })
            }
        }
    }
    return $lines
}

$startedAt = Get-Date
$editor = $null
$cmdLine = ""
$resolvedProjectRoot = ""
$trigger = ""
$triggerDetails = ""
$ueWindowHandle = [IntPtr]::Zero

try {
    $editor = Get-EditorProcess -PidValue $ProcessId
    $cmdLine = Get-CommandLine -PidValue $editor.Id
    $resolvedProjectRoot = if ($ProjectRoot.Trim()) { $ProjectRoot.Trim() } else { Infer-ProjectRoot -CommandLine $cmdLine }

    if (-not $AllowWithoutAttachRenderDoc -and $cmdLine -notmatch "(?i)-AttachRenderDoc") {
        throw "UnrealEditor command line does not contain -AttachRenderDoc. Restart UE with -AttachRenderDoc or pass -AllowWithoutAttachRenderDoc if the log proves RenderDoc is attached."
    }

    if ($TriggerMode -eq "mcp" -or $TriggerMode -eq "auto") {
        try {
            Invoke-McpRenderDocCapture -Url $McpUrl -Launch ([bool]$LaunchRenderDocUi) | Out-Null
            $trigger = "mcp"
            $triggerDetails = "ArtClaw MCP artclaw_renderdoc_capture_frame"
        } catch {
            if ($TriggerMode -eq "mcp") {
                throw
            }
            $triggerDetails = "MCP unavailable, falling back to UI: $($_.Exception.Message)"
        }
    }

    if (-not $trigger) {
        $ueWindowHandle = Invoke-UiRenderDocCapture -EditorProcess $editor
        $trigger = "ui"
        if (-not $triggerDetails) {
            $triggerDetails = "UE Cmd input fallback"
        }
    }

    $searchRoots = @()
    if ($resolvedProjectRoot) {
        $searchRoots += (Join-Path $resolvedProjectRoot "Saved\RenderDocCaptures")
        $searchRoots += (Join-Path $resolvedProjectRoot "Saved")
    }
    $searchRoots += $env:TEMP
    $searchRoots += [Environment]::GetFolderPath("MyDocuments")

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $capture = $null
    do {
        Start-Sleep -Seconds 2
        $capture = Get-LatestCapture -Roots $searchRoots -Since $startedAt.AddSeconds(-2)
    } while ($null -eq $capture -and (Get-Date) -lt $deadline)

    $logEvidence = @(Get-LogEvidence -Root $resolvedProjectRoot)

    if ($null -eq $capture) {
        ConvertTo-JsonResult @{
            success = $false
            message = "RenderDoc command was sent, but no new .rdc was found before timeout."
            processId = $editor.Id
            windowHandle = if ($ueWindowHandle -ne [IntPtr]::Zero) { $ueWindowHandle.ToInt64() } else { 0 }
            projectRoot = $resolvedProjectRoot
            command = $Command
            trigger = $trigger
            triggerDetails = $triggerDetails
            searchedRoots = $searchRoots
            logEvidence = $logEvidence
        } 2
    }

    ConvertTo-JsonResult @{
        success = $true
        message = "RenderDoc capture created."
        processId = $editor.Id
        windowHandle = if ($ueWindowHandle -ne [IntPtr]::Zero) { $ueWindowHandle.ToInt64() } else { 0 }
        projectRoot = $resolvedProjectRoot
        command = $Command
        trigger = $trigger
        triggerDetails = $triggerDetails
        capturePath = $capture.FullName
        captureSizeBytes = $capture.Length
        captureLastWriteTime = $capture.LastWriteTime.ToString("o")
        logEvidence = $logEvidence
    } 0
} catch {
    ConvertTo-JsonResult @{
        success = $false
        message = $_.Exception.Message
        processId = if ($editor) { $editor.Id } else { $ProcessId }
        projectRoot = $resolvedProjectRoot
        commandLine = $cmdLine
        trigger = $trigger
        triggerDetails = $triggerDetails
    } 1
}
