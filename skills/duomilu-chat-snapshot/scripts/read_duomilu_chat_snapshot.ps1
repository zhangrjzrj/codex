param(
  [Parameter(Mandatory = $true)][string]$DeviceId,
  [string]$InstanceId = "",
  [string]$BackendRoot = "D:\hanhan\ai_backend",
  [string]$LogFile = "",
  [int]$MaxLines = 4000
)

$ErrorActionPreference = "Stop"

function Resolve-DefaultLogFile {
  param(
    [string]$BackendRoot,
    [string]$InstanceId
  )

  $date = Get-Date -Format "yyyy-MM-dd"
  $runtimeRoot = Join-Path $BackendRoot "runtime"
  $candidates = New-Object System.Collections.Generic.List[string]

  if (-not [string]::IsNullOrWhiteSpace($InstanceId)) {
    $trimmedInstanceId = $InstanceId.Trim()
    if ($trimmedInstanceId -eq "default") {
      $candidates.Add((Join-Path $runtimeRoot "logs\client-av-debug-$date.log"))
    } else {
      $candidates.Add((Join-Path $runtimeRoot "instances\$trimmedInstanceId\logs\client-av-debug-$date.log"))
    }
  }

  $candidates.Add((Join-Path $runtimeRoot "logs\client-av-debug-$date.log"))

  $instanceLogDirs = Get-ChildItem -LiteralPath (Join-Path $runtimeRoot "instances") -Directory -ErrorAction SilentlyContinue |
    Sort-Object Name
  foreach ($dir in $instanceLogDirs) {
    $candidates.Add((Join-Path $dir.FullName "logs\client-av-debug-$date.log"))
  }

  foreach ($candidate in $candidates | Select-Object -Unique) {
    if (Test-Path -LiteralPath $candidate) {
      return $candidate
    }
  }

  $fallbackDirs = New-Object System.Collections.Generic.List[string]
  if (-not [string]::IsNullOrWhiteSpace($InstanceId)) {
    $trimmedInstanceId = $InstanceId.Trim()
    if ($trimmedInstanceId -eq "default") {
      $fallbackDirs.Add((Join-Path $runtimeRoot "logs"))
    } else {
      $fallbackDirs.Add((Join-Path $runtimeRoot "instances\$trimmedInstanceId\logs"))
    }
  }
  $fallbackDirs.Add((Join-Path $runtimeRoot "logs"))
  foreach ($dir in $instanceLogDirs) {
    $fallbackDirs.Add((Join-Path $dir.FullName "logs"))
  }

  foreach ($dir in $fallbackDirs | Select-Object -Unique) {
    if (-not (Test-Path -LiteralPath $dir)) {
      continue
    }
    $latest = Get-ChildItem -LiteralPath $dir -Filter "client-av-debug-*.log" -File -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending |
      Select-Object -First 1
    if ($latest) {
      return $latest.FullName
    }
  }

  $searched = ($candidates | Select-Object -Unique) -join "; "
  throw "log file not found. searched: $searched"
}

if ([string]::IsNullOrWhiteSpace($LogFile)) {
  $LogFile = Resolve-DefaultLogFile -BackendRoot $BackendRoot -InstanceId $InstanceId
}

if (-not (Test-Path -LiteralPath $LogFile)) {
  throw "log file not found: $LogFile"
}

$lines = Get-Content -LiteralPath $LogFile -Tail $MaxLines
$matched = @()

foreach ($line in $lines) {
  if ([string]::IsNullOrWhiteSpace($line)) {
    continue
  }
  try {
    $row = $line | ConvertFrom-Json
  } catch {
    continue
  }
  $device = $row.device
  $event = $row.event
  if ($null -eq $event) {
    continue
  }
  $eventName = [string]$event.name
  if ($eventName -ne "chat_render_snapshot") {
    continue
  }
  $eventDeviceId = ""
  if ($device -and $device.PSObject.Properties.Name -contains "deviceId") {
    $eventDeviceId = [string]$device.deviceId
  }
  if ($eventDeviceId -ne $DeviceId) {
    continue
  }
  $matched += [PSCustomObject]@{
    server_time = [string]$row.server_time
    session_id = [string]$row.session_id
    event = $event
    device = $device
  }
}

if (-not $matched.Count) {
  throw "no chat_render_snapshot found for device: $DeviceId"
}

$latest = $matched[-1]
$event = $latest.event

$result = [PSCustomObject]@{
  device_id = $DeviceId
  instance_id = $(if ([string]::IsNullOrWhiteSpace($InstanceId)) { "" } else { $InstanceId })
  log_file = $LogFile
  server_time = $latest.server_time
  session_id = [string]$event.session_id
  route = [string]$event.route
  scene_mode = [string]$event.scene_mode
  person_index = $event.person_index
  person_name = [string]$event.person_name
  reason = [string]$event.reason
  message_count = $event.message_count
  active_task = $event.active_task
  visible_messages = $event.visible_messages
}

$result | ConvertTo-Json -Depth 6
