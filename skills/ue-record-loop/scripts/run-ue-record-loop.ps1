[CmdletBinding()]
param(
    [ValidateSet('Local', 'Remote')]
    [string]$Mode = 'Local',
    [Parameter(Mandatory)]
    [string]$RecordCommand,
    [Parameter(Mandatory)]
    [string]$OutputPath,
    [string]$LaunchCommand,
    [string]$RemoteHost,
    [string]$RemoteRecordCommand,
    [string]$RemoteOutputPath,
    [string]$PullDestination,
    [int]$PollSeconds = 5,
    [int]$TimeoutSeconds = 1800
)

$ErrorActionPreference = 'Stop'

function Invoke-CommandChecked {
    param([string]$Command)

    & ([scriptblock]::Create($Command))
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

if ($Mode -eq 'Remote' -and [string]::IsNullOrWhiteSpace($RemoteHost)) {
    throw 'RemoteHost is required in Remote mode.'
}

if ($Mode -eq 'Local' -and $LaunchCommand) {
    Invoke-CommandChecked $LaunchCommand
}

if ($Mode -eq 'Remote' -and $LaunchCommand) {
    & ssh $RemoteHost $LaunchCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Remote launch failed with exit code $LASTEXITCODE"
    }
}

if ($Mode -eq 'Local') {
    Invoke-CommandChecked $RecordCommand
}
elseif ($RemoteRecordCommand) {
    Invoke-CommandChecked $RemoteRecordCommand
}
else {
    & ssh $RemoteHost $RecordCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Remote recording failed with exit code $LASTEXITCODE"
    }
}

$Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
if ($Mode -eq 'Remote') {
    if ([string]::IsNullOrWhiteSpace($RemoteOutputPath)) {
        throw 'RemoteOutputPath is required in Remote mode.'
    }
}
while ($true) {
    $OutputReady = if ($Mode -eq 'Local') {
        Test-Path -LiteralPath $OutputPath
    }
    else {
        & ssh $RemoteHost "if exist \"$RemoteOutputPath\" (exit /b 0) else (exit /b 1)"
        $LASTEXITCODE -eq 0
    }
    if ($OutputReady) {
        break
    }
    if ((Get-Date) -ge $Deadline) {
        $WaitPath = if ($Mode -eq 'Local') { $OutputPath } else { "$RemoteHost`:$RemoteOutputPath" }
        throw "Recording output did not appear before timeout: $WaitPath"
    }
    Start-Sleep -Seconds $PollSeconds
}

if ($Mode -eq 'Remote') {
    if ([string]::IsNullOrWhiteSpace($PullDestination)) {
        throw 'RemoteOutputPath and PullDestination are required in Remote mode.'
    }
    New-Item -ItemType Directory -Force -Path $PullDestination | Out-Null
    & scp -r "$RemoteHost`:$RemoteOutputPath" $PullDestination
    if ($LASTEXITCODE -ne 0) {
        throw "Remote artifact pull failed with exit code $LASTEXITCODE"
    }
}

$Files = Get-ChildItem -LiteralPath $OutputPath -File -Recurse
[pscustomobject]@{
    Mode = $Mode
    OutputPath = $OutputPath
    FileCount = $Files.Count
    Completed = $true
}
