param(
  [string]$ProjectRoot = (Get-Location).Path,
  [string]$Objective = "",
  [string]$Stage = "",
  [string]$NextAction = "",
  [string]$Reason = "one-shot Codex restart requested",
  [string[]]$Completed = @(),
  [string[]]$Evidence = @(),
  [string[]]$StopConditions = @(),
  [string]$Thread = "",
  [string]$TaskId = "",
  [string]$WindowTitle = "",
  [string]$CodexCommand = "codex",
  [switch]$ForkLast,
  [switch]$ResumeLast,
  [switch]$NoFullPermissions,
  [switch]$NoThreadAppend,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$skillRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$checkpointScript = Join-Path $skillRoot "scripts\codex_checkpoint.ps1"
$resumeScript = Join-Path $skillRoot "scripts\codex_resume_project.ps1"

$resolvedProject = (Resolve-Path -LiteralPath $ProjectRoot).Path

$checkpointArgs = @(
  "-ExecutionPolicy", "Bypass",
  "-File", $checkpointScript,
  "-ProjectRoot", $resolvedProject,
  "-Objective", $Objective,
  "-Stage", $Stage,
  "-Reason", $Reason,
  "-NextAction", $NextAction
)

if ($Completed.Count -gt 0) {
  $checkpointArgs += "-Completed"
  $checkpointArgs += ($Completed -join ",")
}
if ($Evidence.Count -gt 0) {
  $checkpointArgs += "-Evidence"
  $checkpointArgs += ($Evidence -join ",")
}
if ($StopConditions.Count -gt 0) {
  $checkpointArgs += "-StopConditions"
  $checkpointArgs += ($StopConditions -join ",")
}
if (-not [string]::IsNullOrWhiteSpace($Thread)) {
  $checkpointArgs += "-Thread"
  $checkpointArgs += $Thread
}
if (-not [string]::IsNullOrWhiteSpace($TaskId)) {
  $checkpointArgs += "-TaskId"
  $checkpointArgs += $TaskId
}
if ($NoThreadAppend) {
  $checkpointArgs += "-NoThreadAppend"
}

$checkpointOutput = & powershell @checkpointArgs
if ($LASTEXITCODE -ne 0) {
  throw "checkpoint failed"
}

$resolvedWindowTitle = $WindowTitle
if ([string]::IsNullOrWhiteSpace($resolvedWindowTitle)) {
  try {
    $resolvedWindowTitle = $host.UI.RawUI.WindowTitle
  } catch {
    $resolvedWindowTitle = ""
  }
}
if ([string]::IsNullOrWhiteSpace($resolvedWindowTitle)) {
  $resolvedWindowTitle = Split-Path -Leaf $resolvedProject
}

$resumeArgs = @(
  "-NoExit",
  "-ExecutionPolicy", "Bypass",
  "-File", $resumeScript,
  "-ProjectRoot", $resolvedProject,
  "-WindowTitle", $resolvedWindowTitle,
  "-CodexCommand", $CodexCommand
)
if ($ForkLast) {
  $resumeArgs += "-ForkLast"
}
if ($ResumeLast) {
  $resumeArgs += "-ResumeLast"
}
if ($NoFullPermissions) {
  $resumeArgs += "-NoFullPermissions"
}

if ($DryRun) {
  $wtCommand = Get-Command wt -ErrorAction SilentlyContinue
  [PSCustomObject]@{
    status = "dry_run"
    project_root = $resolvedProject
    checkpoint_output = ($checkpointOutput -join "`n")
    start_process = if ($wtCommand) { "wt" } else { "powershell" }
    start_args = if ($wtCommand) { @("-w", "0", "new-tab", "--title", $resolvedWindowTitle, "--suppressApplicationTitle", "powershell") + $resumeArgs } else { $resumeArgs }
    note = "DryRun did not start a new Codex process."
  } | ConvertTo-Json -Depth 6
  exit 0
}

$wtCommand = Get-Command wt -ErrorAction SilentlyContinue
if ($wtCommand) {
  & $wtCommand.Source -w 0 new-tab --title $resolvedWindowTitle --suppressApplicationTitle powershell @resumeArgs | Out-Null
} else {
  Start-Process -FilePath "powershell" -ArgumentList $resumeArgs -WindowStyle Normal | Out-Null
}

[PSCustomObject]@{
  status = "restart_worker_started"
  project_root = $resolvedProject
  checkpoint_output = ($checkpointOutput -join "`n")
  window_title = $resolvedWindowTitle
  note = "A new Codex session was started. If Windows Terminal is available, it was opened as a new tab with the same title. Close the old Codex after the new one restores."
} | ConvertTo-Json -Depth 6
