param(
    [string]$VersionKey = "",
    [string]$ConfigPath = "",
    [switch]$Clean,
    [switch]$NoBuild,
    [switch]$ListVersions,
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path (Split-Path -Parent $PSScriptRoot) "references\config.json"
}

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Config not found: $ConfigPath"
}

$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json

if ($ListVersions) {
    $versions = @($config.versions.PSObject.Properties.Name)
    Write-Host "DefaultVersion: $($config.default_version)"
    Write-Host "Versions:"
    foreach ($name in $versions) {
        $item = $config.versions.$name
        [pscustomobject]@{
            VersionKey = $name
            Recipe     = [string]$item.recipe
            BuildDir   = [string]$item.build_dir
            SourceDir  = [string]$item.source_dir
        } | Format-Table -AutoSize
    }
    return
}

if ([string]::IsNullOrWhiteSpace($VersionKey)) {
    $VersionKey = [string]$config.default_version
}

$versions = $config.versions.PSObject.Properties.Name
if ($versions -notcontains $VersionKey) {
    throw "Unknown VersionKey '$VersionKey'. Available: $($versions -join ', ')"
}

$v = $config.versions.$VersionKey
$recipe = [string]$v.recipe
$buildDir = [string]$v.build_dir
$versionWorkdir = if ($v.PSObject.Properties.Name -contains "workdir") {
    [string]$v.workdir
} else {
    ""
}
$workdir = if ([string]::IsNullOrWhiteSpace($versionWorkdir)) {
    [string]$config.default_workdir
} else {
    $versionWorkdir
}
$sourceDir = if ($v.PSObject.Properties.Name -contains "source_dir") {
    [string]$v.source_dir
} else {
    ""
}

foreach ($p in @($recipe, $workdir)) {
    if (-not (Test-Path -LiteralPath $p)) {
        throw "Required path not found: $p"
    }
}

$resolved = [ordered]@{
    VersionKey = $VersionKey
    Workdir    = $workdir
    Recipe     = $recipe
    BuildDir   = $buildDir
    SourceDir  = $sourceDir
    Remote     = [string]$v.remote
    BuildType  = [string]$v.build_type
    Shared     = [bool]$v.shared
    OS         = [string]$v.os
    Arch       = [string]$v.arch
    Compiler   = [string]$v.compiler
    CompilerVersion = [string]$v.compiler_version
    CompilerRuntime = [string]$v.compiler_runtime
}

Write-Host "== resolved config =="
[pscustomobject]$resolved | Format-List

if (-not [string]::IsNullOrWhiteSpace($sourceDir)) {
    if (Test-Path -LiteralPath $sourceDir) {
        Write-Host "SourceDir OK: $sourceDir"
    } else {
        throw "Configured source_dir not found: $sourceDir"
    }
}

if ($ValidateOnly) {
    Write-Host "Validation only requested; skip conan install/build."
    return
}

if ($Clean -and (Test-Path -LiteralPath $buildDir)) {
    Remove-Item -LiteralPath $buildDir -Recurse -Force
}
if (-not (Test-Path -LiteralPath $buildDir)) {
    New-Item -ItemType Directory -Path $buildDir | Out-Null
}

$sharedText = if ([bool]$v.shared) { "True" } else { "False" }

Push-Location $workdir
try {
    $installArgs = @(
        "install", $recipe,
        "-if", $buildDir,
        "-r", [string]$v.remote,
        "-s", "build_type=$($v.build_type)",
        "-o", "shared=$sharedText",
        "-s", "os=$($v.os)",
        "-s", "arch=$($v.arch)",
        "-s", "compiler=$($v.compiler)",
        "-s", "compiler.runtime=$($v.compiler_runtime)",
        "-s", "compiler.version=$($v.compiler_version)"
    )
    Write-Host "== conan $($installArgs -join ' ') =="
    & conan @installArgs
    if ($LASTEXITCODE -ne 0) { throw "conan install failed: $LASTEXITCODE" }

    if (-not $NoBuild) {
        $buildArgs = @("build", $recipe, "-if", $buildDir, "-bf", $buildDir)
        Write-Host "== conan $($buildArgs -join ' ') =="
        & conan @buildArgs
        if ($LASTEXITCODE -ne 0) { throw "conan build failed: $LASTEXITCODE" }
    }
}
finally {
    Pop-Location
}

$dll = Join-Path $buildDir "package\bin\libNewBasisDecoder.dll"
$lib = Join-Path $buildDir "package\lib\libNewBasisDecoder.lib"
$pdb = Join-Path $buildDir "package\pdb\libNewBasisDecoder.pdb"

Write-Host "== outputs =="
foreach ($out in @($dll, $lib, $pdb)) {
    if (Test-Path -LiteralPath $out) {
        Get-Item -LiteralPath $out | Select-Object FullName, Length, LastWriteTime | Format-List
    } else {
        Write-Host "MISSING: $out"
    }
}

if (-not (Test-Path -LiteralPath $dll)) {
    throw "Build did not produce DLL: $dll"
}
