param(
  [string]$ProjectRoot = (Get-Location).Path,
  [string]$Objective = "",
  [string]$Stage = "",
  [string]$NextAction = "",
  [string]$Reason = "",
  [string[]]$Completed = @(),
  [string[]]$Evidence = @(),
  [string[]]$StopConditions = @(),
  [string]$Thread = "",
  [string]$TaskId = "",
  [switch]$NoThreadAppend
)

$ErrorActionPreference = "Stop"

$resolvedProject = (Resolve-Path -LiteralPath $ProjectRoot).Path
$memoryDir = Join-Path $resolvedProject ".codex-memory"
$tasksDir = Join-Path $memoryDir "tasks"
$threadsDir = Join-Path $memoryDir "threads"
New-Item -ItemType Directory -Force -Path $memoryDir, $tasksDir, $threadsDir | Out-Null

if ([string]::IsNullOrWhiteSpace($TaskId)) {
  $TaskId = "task-" + (Get-Date -Format "yyyyMMdd-HHmmss")
}

$gitStatus = ""
try {
  $gitStatus = (git -C $resolvedProject status --short --branch 2>$null) -join "`n"
} catch {
  $gitStatus = ""
}

function Normalize-List {
  param([string[]]$Items)
  $out = New-Object System.Collections.Generic.List[string]
  foreach ($item in $Items) {
    if ([string]::IsNullOrWhiteSpace($item)) { continue }
    $parts = $item -split "\s*,\s*"
    foreach ($part in $parts) {
      if (-not [string]::IsNullOrWhiteSpace($part)) {
        $out.Add($part)
      }
    }
  }
  return @($out.ToArray())
}

$Completed = Normalize-List -Items $Completed
$Evidence = Normalize-List -Items $Evidence
$StopConditions = Normalize-List -Items $StopConditions

$checkpoint = [ordered]@{
  task_id = $TaskId
  updated_at = (Get-Date).ToString("o")
  project_root = $resolvedProject
  objective = $Objective
  stage = $Stage
  reason = $Reason
  completed = $Completed
  evidence = $Evidence
  next_action = $NextAction
  stop_conditions = $StopConditions
  thread = $Thread
  git_status = $gitStatus
}

$currentPath = Join-Path $memoryDir "current-task.json"
$taskPath = Join-Path $tasksDir "$TaskId.json"
$json = $checkpoint | ConvertTo-Json -Depth 8
Set-Content -LiteralPath $currentPath -Value $json -Encoding UTF8
Set-Content -LiteralPath $taskPath -Value $json -Encoding UTF8

if (-not $NoThreadAppend) {
  $threadPath = $null
  if (-not [string]::IsNullOrWhiteSpace($Thread)) {
    if ($Thread.EndsWith(".md")) {
      $threadPath = Join-Path $threadsDir $Thread
    } else {
      $threadPath = Join-Path $threadsDir "$Thread.md"
    }
  } else {
    $threadPath = Join-Path $threadsDir "codex-session-continuity.md"
  }

  $completedText = if ($Completed.Count -gt 0) { ($Completed | ForEach-Object { "- $_" }) -join "`n" } else { "- " }
  $evidenceText = if ($Evidence.Count -gt 0) { ($Evidence | ForEach-Object { "- $_" }) -join "`n" } else { "- " }
  $stopText = if ($StopConditions.Count -gt 0) { ($StopConditions | ForEach-Object { "- $_" }) -join "`n" } else { "- " }
  $entry = @"

## $(Get-Date -Format "yyyy-MM-dd HH:mm:ss") Codex checkpoint
- 当前目标：$Objective
- 当前阶段：$Stage
- 重启/断点原因：$Reason
- 已完成：
$completedText
- 证据：
$evidenceText
- 下一步：$NextAction
- 停止条件：
$stopText
- 状态卡：$currentPath
"@
  Add-Content -LiteralPath $threadPath -Value $entry -Encoding UTF8
}

[PSCustomObject]@{
  status = "checkpoint_written"
  current_task = $currentPath
  task_file = $taskPath
  task_id = $TaskId
} | ConvertTo-Json -Depth 4
