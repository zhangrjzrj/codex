param(
  [string]$ProjectRoot = (Get-Location).Path,
  [string]$CodexCommand = "codex",
  [switch]$ForkLast,
  [switch]$ResumeLast,
  [switch]$NoStart,
  [string]$ExtraPrompt = ""
)

$ErrorActionPreference = "Stop"

$resolvedProject = (Resolve-Path -LiteralPath $ProjectRoot).Path
$memoryDir = Join-Path $resolvedProject ".codex-memory"
$currentPath = Join-Path $memoryDir "current-task.json"
$indexPath = Join-Path $memoryDir "index.md"

$task = $null
if (Test-Path -LiteralPath $currentPath) {
  $task = Get-Content -Raw -LiteralPath $currentPath -Encoding UTF8 | ConvertFrom-Json
}

$objective = if ($task -and $task.objective) { [string]$task.objective } else { "restore current project task" }
$stage = if ($task -and $task.stage) { [string]$task.stage } else { "" }
$nextAction = if ($task -and $task.next_action) { [string]$task.next_action } else { "read project memory and decide the next step" }

$prompt = @"
Restore the current project task and continue execution.

First read:
1. $indexPath
2. $currentPath
3. The relevant thread file referenced by current-task.json

After restoring, report concisely in Chinese:
- current objective
- current stage
- completed work
- current blocker
- next action

Current state summary:
- objective: $objective
- stage: $stage
- next_action: $nextAction

Do not restore the full old chat. Use only project memory and the task state card.
$ExtraPrompt
"@

if ($NoStart) {
  [PSCustomObject]@{
    status = "prompt_generated"
    project_root = $resolvedProject
    prompt = $prompt
  } | ConvertTo-Json -Depth 4
  exit 0
}

if ($ForkLast) {
  & $CodexCommand fork --last -C $resolvedProject $prompt
} elseif ($ResumeLast) {
  & $CodexCommand resume --last -C $resolvedProject $prompt
} else {
  & $CodexCommand -C $resolvedProject $prompt
}
