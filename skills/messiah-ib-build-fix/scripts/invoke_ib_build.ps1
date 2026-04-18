[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$Solution = "",
    [ValidateSet("build", "rebuild", "clean")]
    [string]$Action = "build",
    [string]$Configuration = "Hybrid",
    [string]$Platform = "x64",
    [string]$Project = "",
    [string]$LogDir = "",
    [int]$MaxCpus = 0,
    [switch]$NoMsgs,
    [switch]$ShowTime,
    [switch]$FailFastOnFirstError,
    [int]$FailFastPollMs = 500,
    [string[]]$ExtraArgs = @()
)

$ErrorActionPreference = "Stop"

function Resolve-BuildConsolePath {
    $candidates = @()
    if ($env:IB_BUILDCONSOLE) {
        $candidates += $env:IB_BUILDCONSOLE
    }
    $candidates += @(
        "C:\Program Files (x86)\IncrediBuild\BuildConsole.exe",
        "D:\Program Files (x86)\IncrediBuild\BuildConsole.exe",
        "E:\Program Files (x86)\IncrediBuild\BuildConsole.exe",
        "F:\Program Files (x86)\IncrediBuild\BuildConsole.exe"
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "BuildConsole.exe not found. Set IB_BUILDCONSOLE or install IncrediBuild."
}

function Resolve-RepoRootPath {
    param([string]$InputRoot)

    if ($InputRoot) {
        if (-not (Test-Path -LiteralPath $InputRoot)) {
            throw "RepoRoot does not exist: $InputRoot"
        }
        return (Resolve-Path -LiteralPath $InputRoot).Path
    }

    $cwd = (Get-Location).Path
    $nested = Join-Path $cwd "Messiah"

    if (Test-Path -LiteralPath (Join-Path $nested "Messiah.Windows.sln")) {
        return $nested
    }

    if (Test-Path -LiteralPath (Join-Path $cwd "Messiah.Windows.sln")) {
        return $cwd
    }

    throw "Cannot locate repo root. Run in messiah_h74 root or pass -RepoRoot."
}

function Test-BuildErrorLine {
    param([string]$Line)

    if (-not $Line) {
        return $false
    }

    $clean = $Line.Trim()
    if (-not $clean) {
        return $false
    }

    if ($clean -match '(?i)\bwarning\s+[A-Z]+\d+\b') {
        return $false
    }

    if ($clean -match '(?i)\b(?:fatal error|error)\s+[A-Z]+\d+\b') {
        return $true
    }

    return $false
}

function Stop-ProcessTree {
    param([int]$Pid)

    if ($Pid -le 0) {
        return
    }

    try {
        & taskkill /PID $Pid /T /F | Out-Null
    }
    catch {
        Write-Warning "[messiah-ib-build-fix] failed to stop process tree for pid=$Pid : $($_.Exception.Message)"
    }
}

function Join-CommandLine {
    param([string[]]$Args)

    $quoted = foreach ($a in $Args) {
        if ($null -eq $a) { continue }
        $s = [string]$a
        # Quote args that may be re-parsed by Windows command-line rules or
        # misinterpreted due to shell metacharacters (notably '|').
        if ($s -match '[\s"|\^&<>]') {
            '"' + ($s -replace '"', '\"') + '"'
        }
        else {
            $s
        }
    }

    return ($quoted -join ' ')
}

$repoRootPath = Resolve-RepoRootPath -InputRoot $RepoRoot

$solutionPath = $Solution
if (-not $solutionPath) {
    $solutionPath = Join-Path $repoRootPath "Messiah.Windows.sln"
} elseif (-not [System.IO.Path]::IsPathRooted($solutionPath)) {
    $solutionPath = Join-Path $repoRootPath $solutionPath
}

if (-not (Test-Path -LiteralPath $solutionPath)) {
    throw "Solution file not found: $solutionPath"
}

if (-not $LogDir) {
    $LogDir = Join-Path $repoRootPath ".codex-build\logs"
}

$null = New-Item -ItemType Directory -Path $LogDir -Force

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$baseName = "ib-$Configuration-$Platform-$Action-$stamp"
$outLog = Join-Path $LogDir "$baseName.out.log"
$ibLog = Join-Path $LogDir "$baseName.ib.log"
$metaJson = Join-Path $LogDir "$baseName.meta.json"

$configToken = "$Configuration|$Platform"

# BuildConsole expects VS-style action switches and a /CFG for solution configs.
# - build  : no explicit action switch required
# - rebuild: /REBUILD
# - clean  : /CLEAN
$actionSwitch = ""
switch ($Action) {
    "build" { $actionSwitch = "" }
    "rebuild" { $actionSwitch = "/REBUILD" }
    "clean" { $actionSwitch = "/CLEAN" }
}

$arguments = @(
    $solutionPath,
    "/NOLOGO",
    "/VSVERSION=VC17",
    "/USEMSBUILD=64",
    "/CFG=$configToken",
    "/OUT=$outLog",
    "/LOG=$ibLog",
    "/LOGLEVEL=Basic"
)

if ($actionSwitch) {
    $arguments = @($solutionPath, $actionSwitch) + $arguments[1..($arguments.Count - 1)]
}

if ($Project) {
    $arguments += "/Prj=$Project"
}
if ($NoMsgs) {
    $arguments += "/NOMSGS"
}
if ($ShowTime) {
    $arguments += "/SHOWTIME"
}
if ($MaxCpus -gt 0) {
    $arguments += "/MAXCPUS=$MaxCpus"
}
if ($ExtraArgs -and $ExtraArgs.Count -gt 0) {
    $arguments += $ExtraArgs
}

$buildConsolePath = Resolve-BuildConsolePath
Write-Host "[messiah-ib-build-fix] buildconsole=$buildConsolePath"
Write-Host "[messiah-ib-build-fix] args=$($arguments -join ' ')"

Push-Location $repoRootPath
try {
    $exitCode = -1
    $failFastTriggered = $false
    $failFastReason = ""
    $failFastLine = ""

    if ($FailFastOnFirstError) {
        # Prefer Start-Process for robust argument quoting on Windows PowerShell 5.1.
        $proc = Start-Process `
            -FilePath $buildConsolePath `
            -WorkingDirectory $repoRootPath `
            -ArgumentList $arguments `
            -NoNewWindow `
            -PassThru

        $lastLength = 0L
        $pollMs = [Math]::Max(100, $FailFastPollMs)

        while (-not $proc.HasExited) {
            if (Test-Path -LiteralPath $outLog) {
                try {
                    $item = Get-Item -LiteralPath $outLog -ErrorAction Stop
                    if ($item.Length -ne $lastLength) {
                        $lines = Get-Content -LiteralPath $outLog -ErrorAction Stop
                        $startIndex = 0
                        if ($lastLength -gt 0 -and $lines.Count -gt 200) {
                            $startIndex = [Math]::Max(0, $lines.Count - 200)
                        }
                        for ($i = $startIndex; $i -lt $lines.Count; $i++) {
                            $line = $lines[$i]
                            if (Test-BuildErrorLine -Line $line) {
                                $failFastTriggered = $true
                                $failFastLine = $line.Trim()
                                $failFastReason = "first_error_detected"
                                Write-Host "[messiah-ib-build-fix] fail_fast triggered by: $failFastLine"
                                Stop-ProcessTree -Pid $proc.Id
                                break
                            }
                        }
                        $lastLength = $item.Length
                    }
                }
                catch {
                    Write-Warning "[messiah-ib-build-fix] fail_fast log polling warning: $($_.Exception.Message)"
                }
            }

            if ($failFastTriggered) {
                break
            }

            Start-Sleep -Milliseconds $pollMs
        }

        if (-not $proc.HasExited) {
            try {
                $proc.WaitForExit(5000) | Out-Null
            }
            catch {
            }
        }

        if ($proc.HasExited) {
            $exitCode = $proc.ExitCode
        }
        elseif ($failFastTriggered) {
            $exitCode = 9001
        }
    }
    else {
        & $buildConsolePath @arguments
        $exitCode = $LASTEXITCODE
    }
}
finally {
    Pop-Location
}

$meta = [ordered]@{
    timestamp = (Get-Date).ToString("o")
    repo_root = $repoRootPath
    solution = $solutionPath
    action = $Action
    configuration = $Configuration
    platform = $Platform
    project = $Project
    build_console = $buildConsolePath
    out_log = $outLog
    ib_log = $ibLog
    exit_code = $exitCode
    fail_fast_enabled = [bool]$FailFastOnFirstError
    fail_fast_poll_ms = $FailFastPollMs
    fail_fast_triggered = [bool]$failFastTriggered
    fail_fast_reason = $failFastReason
    fail_fast_line = $failFastLine
}

$meta | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $metaJson -Encoding UTF8

Write-Host "[messiah-ib-build-fix] exit_code=$exitCode"
Write-Host "[messiah-ib-build-fix] out_log=$outLog"
Write-Host "[messiah-ib-build-fix] ib_log=$ibLog"
Write-Host "[messiah-ib-build-fix] meta=$metaJson"

exit $exitCode

