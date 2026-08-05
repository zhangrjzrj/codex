[CmdletBinding(DefaultParameterSetName = 'Window')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Process')]
    [int]$ProcessId,
    [Parameter(Mandatory, ParameterSetName = 'Title')]
    [string]$TitleSubstring,
    [Parameter(Mandatory, ParameterSetName = 'Window')]
    [string]$WindowTitleSubstring,
    [Parameter(Mandatory)]
    [string]$OutputDirectory,
    [Parameter(Mandatory)]
    [string]$TriggerScript,
    [string[]]$TriggerArgumentList = @(),
    [ValidateRange(1, 30)]
    [int]$PostTriggerSeconds = 3,
    [ValidateRange(1, 60)]
    [int]$FramesPerSecond = 30,
    [ValidateRange(1, 60)]
    [int]$ReadyTimeoutSeconds = 30,
    [switch]$CreateVideo,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$outputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$triggerScript = [IO.Path]::GetFullPath($TriggerScript)
if (-not (Test-Path -LiteralPath $triggerScript)) { throw "Trigger script was not found: $triggerScript" }

New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$readyFile = Join-Path $outputDirectory 'ready.signal'
$triggerPath = Join-Path $outputDirectory 'trigger.json'
$recorderLog = Join-Path $outputDirectory 'recorder.log'
$recorderErrorLog = Join-Path $outputDirectory 'recorder.error.log'
foreach ($stalePath in @($readyFile, $triggerPath, $recorderLog, $recorderErrorLog)) {
    if (Test-Path -LiteralPath $stalePath) { Remove-Item -LiteralPath $stalePath -Force }
}

$recorder = Join-Path $PSScriptRoot 'record_window_wgc.ps1'
function ConvertTo-CommandLineArgument([string]$Value) {
    return '"' + $Value.Replace('"', '\"') + '"'
}
$recorderArguments = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (ConvertTo-CommandLineArgument $recorder),
    '-OutputDirectory', (ConvertTo-CommandLineArgument $outputDirectory),
    '-DurationSeconds', $PostTriggerSeconds,
    '-FramesPerSecond', $FramesPerSecond,
    '-ReadyFile', (ConvertTo-CommandLineArgument $readyFile),
    '-Json'
)
if ($PSCmdlet.ParameterSetName -eq 'Process') {
    $recorderArguments += @('-ProcessId', $ProcessId)
} elseif ($PSCmdlet.ParameterSetName -eq 'Title') {
    $recorderArguments += @('-TitleSubstring', (ConvertTo-CommandLineArgument $TitleSubstring))
} else {
    $recorderArguments += @('-WindowTitleSubstring', (ConvertTo-CommandLineArgument $WindowTitleSubstring))
}
if ($CreateVideo) { $recorderArguments += '-CreateVideo' }

$recorderProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList $recorderArguments -PassThru -WindowStyle Hidden -RedirectStandardOutput $recorderLog -RedirectStandardError $recorderErrorLog
$readyDeadline = [DateTime]::UtcNow.AddSeconds($ReadyTimeoutSeconds)
while (-not (Test-Path -LiteralPath $readyFile)) {
    if ($recorderProcess.HasExited) { throw "Recorder exited before becoming ready. See $recorderErrorLog" }
    if ([DateTime]::UtcNow -ge $readyDeadline) {
        Stop-Process -Id $recorderProcess.Id -Force
        throw "Recorder did not become ready within $ReadyTimeoutSeconds seconds."
    }
    Start-Sleep -Milliseconds 50
}

$triggerIssuedAt = (Get-Date).ToString('o')
$global:LASTEXITCODE = 0
& $triggerScript @TriggerArgumentList
$triggerExitCode = $LASTEXITCODE
if ($null -eq $triggerExitCode) { $triggerExitCode = 0 }
if ($triggerExitCode -ne 0) {
    Stop-Process -Id $recorderProcess.Id -Force
    throw "Trigger script failed with exit code $triggerExitCode."
}

$triggerMetadata = [ordered]@{
    triggerIssuedAt = $triggerIssuedAt
    triggerScript = $triggerScript
    triggerArguments = $TriggerArgumentList
    recorderProcessId = $recorderProcess.Id
    postTriggerSeconds = $PostTriggerSeconds
}
$triggerMetadata | ConvertTo-Json | Set-Content -LiteralPath $triggerPath -Encoding utf8

$recorderProcess.WaitForExit()
$recordingMetadataPath = Join-Path $outputDirectory 'recording.json'
if (-not (Test-Path -LiteralPath $recordingMetadataPath)) { throw "Recorder did not produce recording.json. See $recorderErrorLog" }

$result = [ordered]@{
    success = $true
    outputDirectory = $outputDirectory
    readySignal = $readyFile
    triggerMetadata = $triggerPath
    recordingMetadata = $recordingMetadataPath
}
if ($Json) { $result | ConvertTo-Json }
