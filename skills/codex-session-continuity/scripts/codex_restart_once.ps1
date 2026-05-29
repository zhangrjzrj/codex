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
  [string]$CodexCommand = "codex",
  [switch]$ForkLast,
  [switch]$ResumeLast,
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

$resumeArgs = @(
  "-NoExit",
  "-ExecutionPolicy", "Bypass",
  "-File", $resumeScript,
  "-ProjectRoot", $resolvedProject,
  "-CodexCommand", $CodexCommand
)
if ($ForkLast) {
  $resumeArgs += "-ForkLast"
}
if ($ResumeLast) {
  $resumeArgs += "-ResumeLast"
}

if ($DryRun) {
  [PSCustomObject]@{
    status = "dry_run"
    project_root = $resolvedProject
    checkpoint_output = ($checkpointOutput -join "`n")
    start_process = "powershell"
    start_args = $resumeArgs
    note = "DryRun did not start a new Codex process."
  } | ConvertTo-Json -Depth 6
  exit 0
}

Start-Process -FilePath "powershell" -ArgumentList $resumeArgs -WindowStyle Normal | Out-Null

[PSCustomObject]@{
  status = "restart_worker_started"
  project_root = $resolvedProject
  checkpoint_output = ($checkpointOutput -join "`n")
  note = "A new PowerShell window was started to launch a fresh Codex session. Close the old Codex after the new one restores."
} | ConvertTo-Json -Depth 6
