param(
    [ValidateSet("save", "list", "restore")]
    [string]$Action = "save",

    [string]$SnapshotPath = "",

    [string]$CodexCommand = "codex",

    [int]$RecentMinutes = 240,

    [switch]$IncludeCandidates,

    [switch]$NoWindowsTerminal
)

$ErrorActionPreference = "Stop"

function Get-CodexHome {
    if ($env:CODEX_HOME -and $env:CODEX_HOME.Trim()) {
        return $env:CODEX_HOME
    }
    return (Join-Path $HOME ".codex")
}

function Convert-WmiTime {
    param([string]$Value)
    if (-not $Value) { return $null }
    try {
        return [System.Management.ManagementDateTimeConverter]::ToDateTime($Value)
    }
    catch {
        return $null
    }
}

function Get-SessionMeta {
    param([string]$Path)
    try {
        $line = Get-Content -LiteralPath $Path -TotalCount 1 -ErrorAction Stop
        if (-not $line) { return $null }
        $obj = $line | ConvertFrom-Json
        if ($obj.type -ne "session_meta") { return $null }
        return [pscustomobject]@{
            Id = [string]$obj.payload.id
            Cwd = [string]$obj.payload.cwd
            Timestamp = [string]$obj.payload.timestamp
            CliVersion = [string]$obj.payload.cli_version
            Path = $Path
        }
    }
    catch {
        return $null
    }
}

function Find-SessionFileById {
    param(
        [string]$CodexHome,
        [string]$SessionId
    )
    $sessionsRoot = Join-Path $CodexHome "sessions"
    if (-not (Test-Path -LiteralPath $sessionsRoot)) { return $null }
    $match = Get-ChildItem -LiteralPath $sessionsRoot -Recurse -File -Filter "rollout-*.jsonl" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "*$SessionId.jsonl" } |
        Select-Object -First 1
    if ($match) { return $match.FullName }
    return $null
}

function Get-RecentSessions {
    param(
        [string]$CodexHome,
        [int]$Minutes
    )
    $sessionsRoot = Join-Path $CodexHome "sessions"
    if (-not (Test-Path -LiteralPath $sessionsRoot)) { return @() }
    $cutoff = (Get-Date).AddMinutes(-1 * $Minutes)
    return Get-ChildItem -LiteralPath $sessionsRoot -Recurse -File -Filter "rollout-*.jsonl" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $cutoff } |
        Sort-Object LastWriteTime -Descending
}

function Get-ExplicitResumeId {
    param([string]$CommandLine)
    if ($CommandLine -match "(?i)(?:^|\s)resume\s+([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:\s|$)") {
        return $Matches[1]
    }
    return ""
}

function New-SessionRecord {
    param(
        [string]$Kind,
        [string]$Id,
        [string]$Cwd,
        [string]$SessionFile,
        [datetime]$LastWriteTime,
        [object]$Process
    )
    return [pscustomobject]@{
        kind = $Kind
        id = $Id
        cwd = $Cwd
        session_file = $SessionFile
        last_write_time = if ($LastWriteTime) { $LastWriteTime.ToString("o") } else { "" }
        process_id = if ($Process) { [int]$Process.ProcessId } else { $null }
        parent_process_id = if ($Process) { [int]$Process.ParentProcessId } else { $null }
        process_name = if ($Process) { [string]$Process.Name } else { "" }
        process_created = if ($Process) { $created = Convert-WmiTime $Process.CreationDate; if ($created) { $created.ToString("o") } else { "" } } else { "" }
        command_line = if ($Process) { [string]$Process.CommandLine } else { "" }
    }
}

function Save-Snapshot {
    param(
        [string]$CodexHome,
        [string]$OutPath,
        [int]$Minutes
    )
    $processes = Get-CimInstance Win32_Process |
        Where-Object {
            ($_.Name -ieq "codex.exe") -or
            ($_.CommandLine -match "node_modules[/\\]@openai[/\\]codex[/\\]bin[/\\]codex\.js")
        }
    $codexExeProcesses = @($processes | Where-Object { $_.Name -ieq "codex.exe" })

    $records = New-Object System.Collections.Generic.List[object]
    $seen = @{}
    $explicitProcessCount = 0
    $unknownProcessCount = 0

    foreach ($p in $processes) {
        $cmd = [string]$p.CommandLine
        $id = Get-ExplicitResumeId $cmd
        if ($id) {
            if ($p.Name -ieq "codex.exe") { ++$explicitProcessCount }
            $file = Find-SessionFileById -CodexHome $CodexHome -SessionId $id
            $meta = if ($file) { Get-SessionMeta $file } else { $null }
            $cwd = if ($meta) { $meta.Cwd } else { "" }
            $lastWrite = if ($file) { (Get-Item -LiteralPath $file).LastWriteTime } else { $null }
            if (-not $seen.ContainsKey($id)) {
                $records.Add((New-SessionRecord -Kind "explicit" -Id $id -Cwd $cwd -SessionFile $file -LastWriteTime $lastWrite -Process $p))
                $seen[$id] = $true
            }
        }
    }

    $unknownProcessCount = [Math]::Max(0, @($codexExeProcesses).Count - $explicitProcessCount)
    $candidateAdded = 0
    foreach ($f in (Get-RecentSessions -CodexHome $CodexHome -Minutes $Minutes)) {
        if ($candidateAdded -ge $unknownProcessCount) { break }
        $meta = Get-SessionMeta $f.FullName
        if (-not $meta -or -not $meta.Id) { continue }
        if ($seen.ContainsKey($meta.Id)) { continue }
        $records.Add((New-SessionRecord -Kind "candidate" -Id $meta.Id -Cwd $meta.Cwd -SessionFile $f.FullName -LastWriteTime $f.LastWriteTime -Process $null))
        $seen[$meta.Id] = $true
        ++$candidateAdded
    }

    $sessionArray = @($records.ToArray())
    $snapshot = [ordered]@{
        schema = "codex-reboot-restore.v1"
        created_at = (Get-Date).ToString("o")
        machine = $env:COMPUTERNAME
        user = $env:USERNAME
        codex_home = $CodexHome
        recent_minutes = $Minutes
        sessions = $sessionArray
    }

    $dir = Split-Path -Parent $OutPath
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $snapshot | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutPath -Encoding UTF8

    $explicitCount = @($records | Where-Object { $_.kind -eq "explicit" }).Count
    $candidateCount = @($records | Where-Object { $_.kind -eq "candidate" }).Count
    Write-Host "Saved snapshot: $OutPath"
    Write-Host "Explicit sessions: $explicitCount"
    Write-Host "Candidate sessions: $candidateCount"
}

function Load-Snapshot {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Snapshot not found: $Path"
    }
    return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)
}

function Show-Snapshot {
    param([object]$Snapshot)
    Write-Host "Snapshot: $($Snapshot.created_at)"
    Write-Host "Machine: $($Snapshot.machine) User: $($Snapshot.user)"
    foreach ($s in $Snapshot.sessions) {
        $mark = if ($s.kind -eq "explicit") { "exact" } else { "candidate" }
        Write-Host ("[{0}] {1} cwd={2} file={3}" -f $mark, $s.id, $s.cwd, $s.session_file)
    }
}

function Quote-Arg {
    param([string]$Value)
    if ($null -eq $Value) { return '""' }
    return '"' + ($Value -replace '"', '\"') + '"'
}

function Start-CodexSession {
    param(
        [string]$CodexCommand,
        [string]$SessionId,
        [string]$Cwd,
        [bool]$UseWindowsTerminal
    )
    $cdPart = ""
    if ($Cwd -and (Test-Path -LiteralPath $Cwd)) {
        $cdPart = "-C " + (Quote-Arg $Cwd) + " "
    }
    $cmd = "$CodexCommand $cdPart" + "resume $SessionId"

    if ($UseWindowsTerminal) {
        Start-Process wt -ArgumentList @("new-tab", "powershell", "-NoExit", "-Command", $cmd) | Out-Null
    }
    else {
        Start-Process powershell -ArgumentList @("-NoExit", "-Command", $cmd) | Out-Null
    }
}

function Restore-Snapshot {
    param(
        [object]$Snapshot,
        [string]$CodexCommand,
        [bool]$IncludeCandidateSessions,
        [bool]$NoWt
    )
    $useWt = (-not $NoWt) -and [bool](Get-Command wt -ErrorAction SilentlyContinue)
    $sessions = @($Snapshot.sessions | Where-Object { $_.kind -eq "explicit" -or $IncludeCandidateSessions })
    $sessions = @($sessions | Sort-Object kind, id -Unique)

    foreach ($s in $sessions) {
        if (-not $s.id) { continue }
        Write-Host "Opening $($s.kind): $($s.id) $($s.cwd)"
        Start-CodexSession -CodexCommand $CodexCommand -SessionId $s.id -Cwd $s.cwd -UseWindowsTerminal $useWt
        Start-Sleep -Milliseconds 200
    }

    $candidateLeft = @($Snapshot.sessions | Where-Object { $_.kind -eq "candidate" }).Count
    if (-not $IncludeCandidateSessions -and $candidateLeft -gt 0) {
        Write-Host "Candidate sessions were not opened. Re-run restore with -IncludeCandidates to open them."
    }
}

$codexHome = Get-CodexHome
if (-not $SnapshotPath) {
    $SnapshotPath = Join-Path $codexHome "reboot-restore\latest.json"
}

switch ($Action) {
    "save" {
        Save-Snapshot -CodexHome $codexHome -OutPath $SnapshotPath -Minutes $RecentMinutes
    }
    "list" {
        Show-Snapshot -Snapshot (Load-Snapshot $SnapshotPath)
    }
    "restore" {
        Restore-Snapshot -Snapshot (Load-Snapshot $SnapshotPath) -CodexCommand $CodexCommand -IncludeCandidateSessions ([bool]$IncludeCandidates) -NoWt ([bool]$NoWindowsTerminal)
    }
}
