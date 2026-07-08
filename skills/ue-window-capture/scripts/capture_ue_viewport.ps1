param(
    [string]$OutputPath,
    [int]$ProcessId = 0,
    [string]$ProjectRoot = "",
    [int]$Width = 1280,
    [int]$Height = 720,
    [switch]$ForceGameView,
    [string]$McpUrl = "http://127.0.0.1:17881/mcp",
    [switch]$Json
)

$ErrorActionPreference = "Stop"

function Resolve-OutputPath {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
        if (-not [string]::IsNullOrWhiteSpace($ProjectRoot)) {
            return [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot "Saved\CodexEvidence\ue_viewport_$stamp.png"))
        }
        return [System.IO.Path]::GetFullPath((Join-Path (Get-Location) "ue_viewport_$stamp.png"))
    }

    return [System.IO.Path]::GetFullPath($Path)
}

function Get-UnrealProcessInfo {
    param([int]$TargetProcessId)

    $query = "name='UnrealEditor.exe'"
    $processes = Get-CimInstance Win32_Process -Filter $query
    if ($TargetProcessId -gt 0) {
        $processes = $processes | Where-Object { $_.ProcessId -eq $TargetProcessId }
    }
    return $processes | Sort-Object CreationDate -Descending | Select-Object -First 1
}

function Infer-ProjectRoot {
    param([object]$ProcessInfo)

    if (-not [string]::IsNullOrWhiteSpace($ProjectRoot)) {
        return [System.IO.Path]::GetFullPath($ProjectRoot)
    }

    if ($ProcessInfo -and $ProcessInfo.CommandLine -match '([A-Za-z]:\\[^"]+?\.uproject)') {
        return Split-Path -Parent $Matches[1]
    }

    return ""
}

function New-Result {
    param(
        [bool]$Success,
        [string]$Message,
        [object]$ProcessInfo,
        [string]$ResolvedProjectRoot,
        [string]$Warning = "",
        [object]$ArtClawResult = $null
    )

    $exists = Test-Path -LiteralPath $script:ResolvedOutputPath
    $size = 0
    if ($exists) {
        $size = (Get-Item -LiteralPath $script:ResolvedOutputPath).Length
    }

    [pscustomobject]@{
        success = $Success
        message = $Message
        captureMode = "viewport_internal"
        outputPath = $script:ResolvedOutputPath
        metadataPath = [System.IO.Path]::ChangeExtension($script:ResolvedOutputPath, ".json")
        outputExists = $exists
        outputSizeBytes = $size
        width = $Width
        height = $Height
        forceGameView = [bool]$ForceGameView
        processId = if ($ProcessInfo) { $ProcessInfo.ProcessId } else { $null }
        commandLine = if ($ProcessInfo) { $ProcessInfo.CommandLine } else { $null }
        projectRoot = $ResolvedProjectRoot
        mcpUrl = $McpUrl
        artclawRunId = if ($ArtClawResult -and $ArtClawResult.result.structuredContent.run.run_id) { $ArtClawResult.result.structuredContent.run.run_id } else { $null }
        artclawReportPath = if ($ArtClawResult -and $ArtClawResult.result.structuredContent.run.report_file_path) { $ArtClawResult.result.structuredContent.run.report_file_path } else { $null }
        artclawStatus = if ($ArtClawResult -and $ArtClawResult.result.structuredContent.run.status) { $ArtClawResult.result.structuredContent.run.status } else { $null }
        warning = $Warning
        capturedAt = (Get-Date).ToString("o")
    }
}

$script:ResolvedOutputPath = Resolve-OutputPath -Path $OutputPath
$outputDir = Split-Path -Parent $script:ResolvedOutputPath
if (-not [string]::IsNullOrWhiteSpace($outputDir)) {
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
}

$processInfo = Get-UnrealProcessInfo -TargetProcessId $ProcessId
if (-not $processInfo) {
    $result = New-Result -Success $false -Message "No matching UnrealEditor.exe process found." -ProcessInfo $null -ResolvedProjectRoot ""
    $result | ConvertTo-Json -Depth 12 | Set-Content -Path ([System.IO.Path]::ChangeExtension($script:ResolvedOutputPath, ".json")) -Encoding UTF8
    if ($Json) { $result | ConvertTo-Json -Depth 12 }
    exit 2
}

$resolvedProjectRoot = Infer-ProjectRoot -ProcessInfo $processInfo
$forceGameViewText = if ($ForceGameView) { "true" } else { "false" }

$goal = @"
In the currently running Unreal Editor process, take a lightweight viewport screenshot without RenderDoc and without clicking the window.
Use UE Python: unreal.AutomationLibrary.take_high_res_screenshot(res_x=$Width, res_y=$Height, filename=r"$script:ResolvedOutputPath", force_game_view=$forceGameViewText).
Do not modify or save any assets.
Return the actual output path, current level if available, whether PIE is active if available, and any warning.
"@

$body = @{
    jsonrpc = "2.0"
    id = 1
    method = "tools/call"
    params = @{
        name = "artclaw_run_task"
        arguments = @{
            task_type = "editor_viewport_screenshot"
            caller = "codex-ue-window-capture"
            return_immediately = $false
            goal = $goal
            constraints = @{
                no_renderdoc = $true
                no_asset_modification = $true
                output_path = $script:ResolvedOutputPath
                width = $Width
                height = $Height
                force_game_view = [bool]$ForceGameView
            }
            context = @{
                project_root = $resolvedProjectRoot
                process_id = $processInfo.ProcessId
            }
        }
    }
} | ConvertTo-Json -Depth 12

try {
    $artclawResult = Invoke-RestMethod -Uri $McpUrl -Method Post -ContentType "application/json" -Body $body -TimeoutSec 120
}
catch {
    $result = New-Result -Success $false -Message ("ArtClaw MCP call failed: " + $_.Exception.Message) -ProcessInfo $processInfo -ResolvedProjectRoot $resolvedProjectRoot
    $result | ConvertTo-Json -Depth 12 | Set-Content -Path ([System.IO.Path]::ChangeExtension($script:ResolvedOutputPath, ".json")) -Encoding UTF8
    if ($Json) { $result | ConvertTo-Json -Depth 12 }
    exit 3
}

$isError = $false
if ($artclawResult.result -and $null -ne $artclawResult.result.isError) {
    $isError = [bool]$artclawResult.result.isError
}

$exists = Test-Path -LiteralPath $script:ResolvedOutputPath
$success = (-not $isError) -and $exists
$message = if ($success) { "Captured UE viewport through ArtClaw MCP." } else { "ArtClaw completed but screenshot file was not produced." }
$warning = if ($success) { "" } else { "Check ArtClaw report and UE log for screenshot failure details." }

$result = New-Result -Success $success -Message $message -ProcessInfo $processInfo -ResolvedProjectRoot $resolvedProjectRoot -Warning $warning -ArtClawResult $artclawResult
$result | ConvertTo-Json -Depth 12 | Set-Content -Path ([System.IO.Path]::ChangeExtension($script:ResolvedOutputPath, ".json")) -Encoding UTF8

if ($Json) {
    $result | ConvertTo-Json -Depth 12
}
else {
    Write-Output $script:ResolvedOutputPath
}

if (-not $success) {
    exit 4
}
