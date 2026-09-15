param(
    [Parameter(Mandatory = $true)][string]$OfficialPackage,
    [Parameter(Mandatory = $true)][string]$CompletePackage,
    [Parameter(Mandatory = $true)][string]$GeneratedAssets,
    [Parameter(Mandatory = $true)][string]$NbsFile,
    [string]$NbsName = "H74.nbs"
)

$ErrorActionPreference = "Stop"
$official = (Resolve-Path -LiteralPath $OfficialPackage).Path
$complete = (Resolve-Path -LiteralPath $CompletePackage).Path
$assets = [System.IO.Path]::GetFullPath($GeneratedAssets)
$nbs = (Resolve-Path -LiteralPath $NbsFile).Path
$package = Join-Path $assets "Package"

New-Item -ItemType Directory -Force -Path $assets, $package | Out-Null
robocopy $official $package /MIR /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) { throw "Official Package copy failed: robocopy exit $LASTEXITCODE" }

foreach ($name in @("Script", "UIScript", "Videos")) {
    $source = Join-Path $complete $name
    if (Test-Path -LiteralPath $source) {
        robocopy $source (Join-Path $package $name) /E /NFL /NDL /NJH /NJS /NP
        if ($LASTEXITCODE -ge 8) { throw "$name overlay failed: robocopy exit $LASTEXITCODE" }
    }
}

# Full UI data may contain non-Android mappings, so restore every official UI file last.
robocopy (Join-Path $official "UIScript") (Join-Path $package "UIScript") /E /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) { throw "Official UIScript restore failed: robocopy exit $LASTEXITCODE" }

$videoDir = Join-Path $package "Videos"
New-Item -ItemType Directory -Force -Path $videoDir | Out-Null
Copy-Item -LiteralPath $nbs -Destination (Join-Path $videoDir $NbsName) -Force
Set-Content -LiteralPath (Join-Path $assets "assets.lst") -Encoding ascii -Value @("Engine", "netease_data", "Package")

$required = @("Script\Python\main.py", "UIScript\textureinfo.info", "UIScript\plists", ("Videos\" + $NbsName))
foreach ($relative in $required) {
    $path = Join-Path $package $relative
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required Package file missing: $relative" }
    if ((Get-Item -LiteralPath $path).Length -eq 0) { throw "Required Package file is empty: $relative" }
}

[pscustomobject]@{ status = "success"; package = $package; nbs = (Join-Path $videoDir $NbsName); roots = "Engine,netease_data,Package" } | ConvertTo-Json
