param(
    [ValidateSet("save", "list", "restore")]
    [string]$Action = "save",

    [string]$SnapshotPath = "",

    [string]$CodexCommand = "codex",

    [int]$RecentMinutes = 240,

    [switch]$IncludeCandidates,

    [switch]$NoWindowsTerminal,

    [switch]$NoFullAccess,

    [string]$ModelProvider = "",

    [string]$Model = "",

    [switch]$NoColorRestore,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Get-CodexHome {
    if ($env:CODEX_HOME -and $env:CODEX_HOME.Trim()) {
        return $env:CODEX_HOME
    }
    return (Join-Path $HOME ".codex")
}

function Get-ConfiguredModelProvider {
    param([string]$CodexHome)
    $configPath = Join-Path $CodexHome "config.toml"
    if (-not (Test-Path -LiteralPath $configPath)) { return "" }
    $match = Select-String -LiteralPath $configPath -Pattern '^\s*model_provider\s*=\s*["'']([^"'']+)["'']\s*(?:#.*)?$' | Select-Object -First 1
    if ($match -and $match.Matches.Count -gt 0) { return $match.Matches[0].Groups[1].Value }
    return ""
}

function Resolve-WindowsTerminal {
    $cmd = Get-Command wt.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\wt.exe'),
        (Join-Path $env:ProgramFiles 'WindowsApps\Microsoft.WindowsTerminal_8wekyb3d8bbwe\wt.exe')
    )
    foreach ($path in $candidates) {
        if ($path -and (Test-Path -LiteralPath $path)) { return $path }
    }
    return $null
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

function Get-WindowTitleMapPath {
    param([string]$CodexHome)
    return (Join-Path $CodexHome "reboot-restore\window-titles.json")
}

function Load-WindowTitleMap {
    param([string]$CodexHome)
    $path = Get-WindowTitleMapPath -CodexHome $CodexHome
    if (-not (Test-Path -LiteralPath $path)) { return @{} }
    try {
        $obj = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
        $map = @{}
        foreach ($prop in $obj.PSObject.Properties) {
            $map[$prop.Name] = [string]$prop.Value
        }
        return $map
    }
    catch {
        return @{}
    }
}

function Get-SessionDeclaredTitle {
    param([string]$SessionFile)
    if (-not $SessionFile -or -not (Test-Path -LiteralPath $SessionFile)) { return "" }

    $patterns = @(
        "(?i)/rename\s+(.+)$",
        "当前窗口主题[:：]\s*(.+)$",
        "窗口主题[:：]\s*(.+)$",
        "把(?:这个|当前)?窗口(?:记为|命名为|设为|设置为)[:：]?\s*(.+)$"
    )

    try {
        $fileInfo = Get-Item -LiteralPath $SessionFile -ErrorAction Stop
        $maxBytes = 524288
        $fs = [System.IO.File]::Open($fileInfo.FullName, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        try {
            $start = [Math]::Max(0, $fs.Length - $maxBytes)
            $fs.Seek($start, [System.IO.SeekOrigin]::Begin) | Out-Null
            $buffer = New-Object byte[] ([int]($fs.Length - $start))
            $read = $fs.Read($buffer, 0, $buffer.Length)
        }
        finally {
            $fs.Dispose()
        }
        if ($read -le 0) { return "" }
        $text = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $read)
        $lines = $text -split "`r?`n"
        [array]::Reverse($lines)
        foreach ($line in $lines) {
            foreach ($pattern in $patterns) {
                if ($line -match $pattern) {
                    $title = [string]$Matches[1]
                    $title = $title -replace '\\n.*$', ''
                    $title = $title -replace '[",，。]+$', ''
                    $title = $title.Trim()
                    if ($title) { return $title }
                }
            }
        }
    }
    catch {
        return ""
    }

    return ""
}

function Get-ProcessWindowTitle {
    param(
        [object]$Process,
        [hashtable]$ProcessById
    )
    if (-not $Process) { return "" }

    $current = $Process
    for ($i = 0; $i -lt 4 -and $current; ++$i) {
        try {
            $gp = Get-Process -Id ([int]$current.ProcessId) -ErrorAction SilentlyContinue
            $title = if ($gp) { [string]$gp.MainWindowTitle } else { "" }
            if ($title) {
                $name = [string]$current.Name
                if ($name -in @("codex.exe", "node.exe", "powershell.exe", "cmd.exe")) {
                    if ($title -notmatch "^(Windows PowerShell|Administrator: Windows PowerShell|Command Prompt)$") {
                        return $title.Trim()
                    }
                }
            }
        }
        catch {
        }

        if (-not $current.ParentProcessId -or -not $ProcessById.ContainsKey([int]$current.ParentProcessId)) { break }
        $current = $ProcessById[[int]$current.ParentProcessId]
    }

    return ""
}

function Resolve-SessionTitle {
    param(
        [string]$Id,
        [string]$SessionFile,
        [object]$Process,
        [hashtable]$ProcessById,
        [hashtable]$TitleMap
    )

    if ($Id -and $TitleMap.ContainsKey($Id) -and $TitleMap[$Id]) {
        return [pscustomobject]@{ Title = [string]$TitleMap[$Id]; Source = "map" }
    }

    $declared = Get-SessionDeclaredTitle -SessionFile $SessionFile
    if ($declared) {
        return [pscustomobject]@{ Title = $declared; Source = "session" }
    }

    $processTitle = Get-ProcessWindowTitle -Process $Process -ProcessById $ProcessById
    if ($processTitle) {
        return [pscustomobject]@{ Title = $processTitle; Source = "process" }
    }

    return [pscustomobject]@{ Title = ""; Source = "" }
}

function Get-FallbackTitle {
    param(
        [string]$Cwd,
        [string]$Id
    )
    if ($Cwd) {
        try {
            $leaf = Split-Path -Leaf $Cwd
            if ($leaf) { return $leaf }
        }
        catch {
        }
    }
    if ($Id -and $Id.Length -ge 8) {
        return "codex-" + $Id.Substring(0, 8)
    }
    return "codex"
}

function New-SessionRecord {
    param(
        [string]$Kind,
        [string]$Id,
        [string]$Cwd,
        [string]$SessionFile,
        [datetime]$LastWriteTime,
        [object]$Process,
        [string]$Title,
        [string]$TitleSource
    )
    $resolvedTitle = if ($Title) { $Title } else { Get-FallbackTitle -Cwd $Cwd -Id $Id }
    $resolvedTitleSource = if ($TitleSource) { $TitleSource } elseif ($resolvedTitle) { "fallback" } else { "" }
    return [pscustomobject]@{
        kind = $Kind
        id = $Id
        title = if ($resolvedTitle) { $resolvedTitle } else { "" }
        title_source = if ($resolvedTitleSource) { $resolvedTitleSource } else { "" }
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
    $allProcesses = Get-CimInstance Win32_Process
    $processById = @{}
    foreach ($proc in $allProcesses) {
        $processById[[int]$proc.ProcessId] = $proc
    }
    $titleMap = Load-WindowTitleMap -CodexHome $CodexHome
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
                $titleInfo = Resolve-SessionTitle -Id $id -SessionFile $file -Process $p -ProcessById $processById -TitleMap $titleMap
                $records.Add((New-SessionRecord -Kind "explicit" -Id $id -Cwd $cwd -SessionFile $file -LastWriteTime $lastWrite -Process $p -Title $titleInfo.Title -TitleSource $titleInfo.Source))
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
        $titleInfo = Resolve-SessionTitle -Id $meta.Id -SessionFile $f.FullName -Process $null -ProcessById $processById -TitleMap $titleMap
        $records.Add((New-SessionRecord -Kind "candidate" -Id $meta.Id -Cwd $meta.Cwd -SessionFile $f.FullName -LastWriteTime $f.LastWriteTime -Process $null -Title $titleInfo.Title -TitleSource $titleInfo.Source))
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
        $title = if ($s.PSObject.Properties.Name -contains "title") { [string]$s.title } else { "" }
        $source = if ($s.PSObject.Properties.Name -contains "title_source") { [string]$s.title_source } else { "" }
        if ($title) {
            Write-Host ("[{0}] {1} title={2} source={3} cwd={4} file={5}" -f $mark, $s.id, $title, $source, $s.cwd, $s.session_file)
        }
        else {
            Write-Host ("[{0}] {1} cwd={2} file={3}" -f $mark, $s.id, $s.cwd, $s.session_file)
        }
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
        [string]$Title,
        [bool]$UseWindowsTerminal,
        [bool]$FullAccess,
        [string]$ModelProvider,
        [string]$Model,
        [bool]$RestoreColor,
        [bool]$DryRun
    )
    $cdPart = ""
    if ($Cwd -and (Test-Path -LiteralPath $Cwd)) {
        $cdPart = "-C " + (Quote-Arg $Cwd) + " "
    }
    $accessPart = if ($FullAccess) { "--dangerously-bypass-approvals-and-sandbox " } else { "" }
    $providerPart = if ($ModelProvider) { "-c " + (Quote-Arg ("model_provider=" + $ModelProvider)) + " " } else { "" }
    $modelPart = if ($Model) { "-m " + (Quote-Arg $Model) + " " } else { "" }
    $colorPart = if ($RestoreColor) {
        '[Environment]::SetEnvironmentVariable(''NO_COLOR'', $null, ''Process''); $env:TERM = ''xterm-256color''; $env:COLORTERM = ''truecolor''; '
    }
    else {
        ""
    }
    $cmd = $colorPart + "$CodexCommand $accessPart$cdPart" + "resume $SessionId $providerPart$modelPart"

    if ($UseWindowsTerminal) {
        $args = @("new-tab")
        if ($Title) {
            $args += @("--title", $Title)
        }
        $args += @("powershell", "-NoExit", "-Command", $cmd)
        if ($DryRun) {
            Write-Host ("DRY-RUN wt {0}" -f (($args | ForEach-Object { Quote-Arg $_ }) -join " "))
            return
        }
        $wtPath = Resolve-WindowsTerminal
        if (-not $wtPath) { throw 'Windows Terminal (wt.exe) not found' }
        & $wtPath @args | Out-Null
    }
    else {
        $titlePart = if ($Title) { '$host.UI.RawUI.WindowTitle = ' + (Quote-Arg $Title) + '; ' } else { "" }
        if ($DryRun) {
            Write-Host ("DRY-RUN powershell -NoExit -Command {0}" -f (Quote-Arg ($titlePart + $cmd)))
            return
        }
        Start-Process powershell -ArgumentList @("-NoExit", "-Command", ($titlePart + $cmd)) | Out-Null
    }
}

function Restore-Snapshot {
    param(
        [object]$Snapshot,
        [string]$CodexCommand,
        [bool]$IncludeCandidateSessions,
        [bool]$NoWt,
        [bool]$FullAccess,
        [string]$ModelProvider,
        [string]$Model,
        [bool]$RestoreColor,
        [bool]$DryRun
    )
    $useWt = (-not $NoWt) -and [bool](Get-Command wt -ErrorAction SilentlyContinue)
    $sessions = @($Snapshot.sessions | Where-Object { $_.kind -eq "explicit" -or $IncludeCandidateSessions })
    $sessions = @($sessions | Sort-Object kind, id -Unique)

    foreach ($s in $sessions) {
        if (-not $s.id) { continue }
        $accessLabel = if ($FullAccess) { "full-access" } else { "normal" }
        $title = if ($s.PSObject.Properties.Name -contains "title") { [string]$s.title } else { "" }
        $titleLabel = if ($title) { " title=$title" } else { "" }
        Write-Host "Opening $($s.kind) [$accessLabel]: $($s.id) $($s.cwd)$titleLabel"
        Start-CodexSession -CodexCommand $CodexCommand -SessionId $s.id -Cwd $s.cwd -Title $title -UseWindowsTerminal $useWt -FullAccess $FullAccess -ModelProvider $ModelProvider -Model $Model -RestoreColor $RestoreColor -DryRun $DryRun
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
        if (-not $ModelProvider) { $ModelProvider = Get-ConfiguredModelProvider -CodexHome $codexHome }
        Restore-Snapshot -Snapshot (Load-Snapshot $SnapshotPath) -CodexCommand $CodexCommand -IncludeCandidateSessions ([bool]$IncludeCandidates) -NoWt ([bool]$NoWindowsTerminal) -FullAccess (-not [bool]$NoFullAccess) -ModelProvider $ModelProvider -Model $Model -RestoreColor (-not [bool]$NoColorRestore) -DryRun ([bool]$DryRun)
    }
}
