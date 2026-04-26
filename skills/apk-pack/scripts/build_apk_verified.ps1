param(
  [Parameter(Mandatory = $true)][string]$ProjectPath,
  [Parameter(Mandatory = $true)][string]$PackageName,
  [ValidateSet('auto', 'local', 'cloud')][string]$Mode = 'local',
  [string]$HBuilderXCli = 'D:\hanhan\HBuilderX\cli.exe',
  [string]$OfflineProjectPath = '',
  [string]$AndroidSdkDir = 'D:\AndroidSDK',
  [Parameter(ValueFromRemainingArguments = $true)][string[]]$ExtraArgs
)

$ErrorActionPreference = 'Stop'

function Get-AppIdFromManifest([string]$manifestPath) {
  $raw = Get-Content -LiteralPath $manifestPath -Raw
  $m = [regex]::Match($raw, '"appid"\s*:\s*"([^"]+)"')
  if (-not $m.Success) {
    throw "appid not found in manifest.json: $manifestPath"
  }
  return $m.Groups[1].Value
}

function Get-VerifyTag([string]$projectPath) {
  $tagFile = Join-Path $projectPath '.apk_verify_tag'
  if (-not (Test-Path -LiteralPath $tagFile)) {
    throw "verify tag file missing: $tagFile"
  }
  $raw = Get-Content -LiteralPath $tagFile -Raw
  $tag = ($raw -split "(`r`n|`n|`r)")[0].Trim()
  if ([string]::IsNullOrWhiteSpace($tag)) {
    throw "verify tag is empty in file: $tagFile"
  }
  return $tag
}

function Resolve-AppServicePath([string]$projectPath, [string]$appId) {
  $candidates = @(
    (Join-Path $projectPath "unpackage\resources\$appId\www\app-service.js"),
    (Join-Path $projectPath "unpackage\cache\wgt\$appId\app-service.js")
  )
  foreach ($p in $candidates) {
    if (Test-Path -LiteralPath $p) { return $p }
  }
  throw "app-service.js not found in expected paths for appid=$appId"
}

$verifyTag = Get-VerifyTag $ProjectPath

$publishOutput = & $HBuilderXCli publish app-android --type appResource --project $ProjectPath 2>&1
if ($LASTEXITCODE -ne 0) {
  throw "publish appResource failed: $($publishOutput -join "`n")"
}

$appId = Get-AppIdFromManifest (Join-Path $ProjectPath 'manifest.json')
$appServicePath = Resolve-AppServicePath $ProjectPath $appId
$match = Select-String -Path $appServicePath -Pattern [regex]::Escape($verifyTag) -SimpleMatch -ErrorAction SilentlyContinue
if (-not $match) {
  throw "verify tag '$verifyTag' not found in exported app-service.js: $appServicePath"
}

& "$PSScriptRoot\build_apk.ps1" `
  -ProjectPath $ProjectPath `
  -PackageName $PackageName `
  -Mode $Mode `
  -HBuilderXCli $HBuilderXCli `
  -OfflineProjectPath $OfflineProjectPath `
  -AndroidSdkDir $AndroidSdkDir
