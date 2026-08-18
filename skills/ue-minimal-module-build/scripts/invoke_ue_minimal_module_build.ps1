param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,

    [Parameter(Mandatory = $true)]
    [string]$Uproject,

    [Parameter(Mandatory = $true)]
    [string]$Target,

    [string]$Platform = "Win64",

    [string]$Configuration = "Development",

    [Parameter(Mandatory = $true)]
    [string]$Module,

    [string]$EngineRoot = "F:\L46\L46_trunk\Engine_Release\Engine5.6\Windows\Engine",

    [switch]$AllowXGE
)

$ErrorActionPreference = "Stop"

$buildBat = Join-Path $EngineRoot "Build\BatchFiles\Build.bat"
if (-not (Test-Path -LiteralPath $buildBat)) {
    throw "Build.bat not found: $buildBat"
}

if (-not (Test-Path -LiteralPath $Uproject)) {
    throw "uproject not found: $Uproject"
}

$arguments = @(
    $Target
    $Platform
    $Configuration
    "-Project=$Uproject"
    "-WaitMutex"
    "-FromMsBuild"
    "-Module=$Module"
)

if (-not $AllowXGE) {
    $arguments += "-NoXGE"
}

Write-Host "[ue-minimal-module-build] ProjectRoot=$ProjectRoot"
Write-Host "[ue-minimal-module-build] Target=$Target Platform=$Platform Configuration=$Configuration Module=$Module"
Write-Host "[ue-minimal-module-build] Command=$buildBat $($arguments -join ' ')"

Push-Location $ProjectRoot
try {
    & $buildBat @arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "UBT failed with exit code $exitCode"
    }
}
finally {
    Pop-Location
}

Write-Host "[ue-minimal-module-build] Build succeeded."
