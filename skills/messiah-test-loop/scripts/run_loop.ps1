[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("aov_record", "nbs_playback", "cli_playback", "cli_record")]
    [string]$Scenario,
    [int]$MaxRounds = 1,
    [bool]$DoBuild = $true,
    [bool]$RequireApproval = $true,
    [string]$RepoRoot = "E:\messiah_h74",
    [string]$ServerProfile = "",
    [int]$SpaceType = 2,
    [int]$Spaceno = 98121,
    [int]$ShipConfigId = 9,
    [string]$Account = "",
    [ValidateSet("after_connect", "after_operator_load", "after_click_start", "after_login", "after_scenario")]
    [string]$StopPoint = "after_click_start",
    [int]$TimeoutConnect = 60,
    [int]$TimeoutLoginUI = 60,
    [int]$ClickMaxAttempts = 5,
    [double]$ClickIntervalSec = 0.5,
    [bool]$CaptureOnPlaybackStart = $false,
    [int]$CaptureDelayFrames = 20,
    [int]$CaptureTargetFrame = 0,
    [ValidateSet("target_window", "target_frame_single")]
    [string]$CaptureTargetMode = "target_window",
    [ValidateSet("nbs", "actual")]
    [string]$CaptureFrameMode = "nbs",
    [int]$CaptureWindowSize = 5,
    [int]$CapturePreRoll = 2,
    [bool]$AbortOnTraceNotice = $false,
    [bool]$AbortOnProcessExit = $true,
    [bool]$RequestExitOnFinish = $false,
    [string]$CliMontId = "",
    [string]$CliNbs = "",
    [int]$CliStart = 0,
    [int]$CliEnd = 0,
    [bool]$AnalyzeRdc = $false,
    [string]$AnalyzeRdcPath = "",
    [string]$AnalyzeRdcPassKeyword = "WaterPass",
    [ValidateSet("pixel", "vertex", "compute")]
    [string]$AnalyzeRdcStage = "pixel",
    [int]$AnalyzeRdcTimeout = 180,
    [string]$AnalyzeRdcQrenderdocPath = "",
    [int]$AnalyzeRdcTargetEventId = 0,
    [ValidateSet("layered", "strict", "aggressive")]
    [string]$AnalyzeRdcCbValueMode = "layered",
    [int]$AnalyzeRdcCbTopN = 20,
    [int]$AnalyzeRdcCbNeighborWindow = 3,
    [bool]$AnalyzeRdcCbNonzeroOnly = $false
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyScript = Join-Path $scriptDir "run_loop.py"

$args = @(
    $pyScript,
    "--scenario", $Scenario,
    "--max-rounds", $MaxRounds,
    "--do-build", $DoBuild,
    "--require-approval", $RequireApproval,
    "--repo-root", $RepoRoot,
    "--space-type", $SpaceType,
    "--spaceno", $Spaceno,
    "--ship-config-id", $ShipConfigId,
    "--stop-point", $StopPoint,
    "--timeout-connect", $TimeoutConnect,
    "--timeout-login-ui", $TimeoutLoginUI,
    "--click-max-attempts", $ClickMaxAttempts,
    "--click-interval-sec", $ClickIntervalSec,
    "--capture-on-playback-start", $CaptureOnPlaybackStart,
    "--capture-delay-frames", $CaptureDelayFrames,
    "--capture-target-frame", $CaptureTargetFrame,
    "--capture-target-mode", $CaptureTargetMode,
    "--capture-frame-mode", $CaptureFrameMode,
    "--capture-window-size", $CaptureWindowSize,
    "--capture-pre-roll", $CapturePreRoll,
    "--abort-on-trace-notice", $AbortOnTraceNotice,
    "--abort-on-process-exit", $AbortOnProcessExit,
    "--request-exit-on-finish", $RequestExitOnFinish,
    "--analyze-rdc", $AnalyzeRdc,
    "--analyze-rdc-pass-keyword", $AnalyzeRdcPassKeyword,
    "--analyze-rdc-stage", $AnalyzeRdcStage,
    "--analyze-rdc-timeout", $AnalyzeRdcTimeout,
    "--analyze-rdc-target-event-id", $AnalyzeRdcTargetEventId,
    "--analyze-rdc-cb-value-mode", $AnalyzeRdcCbValueMode,
    "--analyze-rdc-cb-top-n", $AnalyzeRdcCbTopN,
    "--analyze-rdc-cb-neighbor-window", $AnalyzeRdcCbNeighborWindow,
    "--analyze-rdc-cb-nonzero-only", $AnalyzeRdcCbNonzeroOnly
)

if (-not [string]::IsNullOrWhiteSpace($CliMontId)) {
    $args += @("--cli-montid", $CliMontId)
}
if (-not [string]::IsNullOrWhiteSpace($CliNbs)) {
    $args += @("--cli-nbs", $CliNbs)
}
$args += @("--cli-start", $CliStart)
$args += @("--cli-end", $CliEnd)

if (-not [string]::IsNullOrWhiteSpace($ServerProfile)) {
    $args += @("--server-profile", $ServerProfile)
}

if (-not [string]::IsNullOrWhiteSpace($Account)) {
    $args += @("--account", $Account)
}

if (-not [string]::IsNullOrWhiteSpace($AnalyzeRdcPath)) {
    $args += @("--analyze-rdc-path", $AnalyzeRdcPath)
}

if (-not [string]::IsNullOrWhiteSpace($AnalyzeRdcQrenderdocPath)) {
    $args += @("--analyze-rdc-qrenderdoc-path", $AnalyzeRdcQrenderdocPath)
}

Write-Host "[messiah-test-loop] python $($args -join ' ')"
& python @args
exit $LASTEXITCODE
