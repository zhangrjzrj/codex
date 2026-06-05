param(
  [Parameter(Mandatory = $true)][string]$ProjectPath,
  [Parameter(Mandatory = $true)][string]$PackageName,
  [ValidateSet('auto', 'local', 'cloud')][string]$Mode = 'local',
  [string]$HBuilderXCli = 'D:\hanhan\HBuilderX\cli.exe',
  [string]$OutputDir = '',
  [switch]$DownloadApk,
  [string]$OfflineSdkZipPath = '',
  [string]$OfflineSdkExtractDir = 'D:\hanhan\offline-pack\android-sdk',
  [string]$OfflineProjectPath = '',
  [string]$AndroidSdkDir = 'D:\AndroidSDK',
  [Parameter(ValueFromRemainingArguments = $true)][string[]]$ExtraArgs
)

$ErrorActionPreference = 'Stop'
$script:VerifyTag = ''

function Resolve-VerifyTag {
  $tagFile = Join-Path $ProjectPath '.apk_verify_tag'
  if (Test-Path -LiteralPath $tagFile) {
    $raw = Get-Content -LiteralPath $tagFile -Raw
    $tag = ($raw -split "(`r`n|`n|`r)")[0].Trim()
    if (-not [string]::IsNullOrWhiteSpace($tag)) {
      return $tag
    }
  }
  if (-not [string]::IsNullOrWhiteSpace($env:APK_VERIFY_TAG)) {
    return [string]$env:APK_VERIFY_TAG
  }
  return ''
}

function Ensure-BaseValidation {
  if (-not (Test-Path -LiteralPath $HBuilderXCli)) {
    throw "HBuilderX cli not found: $HBuilderXCli"
  }
  if (-not (Test-Path -LiteralPath $ProjectPath)) {
    throw "Project path not found: $ProjectPath"
  }
  $manifestPath = Join-Path $ProjectPath 'manifest.json'
  if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "manifest.json not found under project: $ProjectPath"
  }
}

function Ensure-OutputDir([string]$DefaultSubdir) {
  if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $script:OutputDir = Join-Path $ProjectPath $DefaultSubdir
  }
  New-Item -ItemType Directory -Force -Path $script:OutputDir | Out-Null
}

function Write-ResultAndExit(
  [string]$status,
  [string]$modeUsed,
  [string]$packLogPath,
  [string]$downloadUrl,
  [string]$downloadedApkPath,
  [string]$localApkPath
) {
  $result = [PSCustomObject]@{
    status              = $status
    mode_used           = $modeUsed
    pack_log_path       = $packLogPath
    download_url        = $downloadUrl
    downloaded_apk_path = $downloadedApkPath
    local_apk_path      = $localApkPath
  }
  $result | ConvertTo-Json -Depth 5
  if ($status -ne 'success') { exit 2 }
  exit 0
}

function Get-AppIdFromManifest {
  $manifestPath = Join-Path $ProjectPath 'manifest.json'
  $raw = Get-Content -LiteralPath $manifestPath -Raw
  $m = [regex]::Match($raw, '"appid"\s*:\s*"([^"]+)"')
  $appId = if ($m.Success) { $m.Groups[1].Value } else { '' }
  if ([string]::IsNullOrWhiteSpace($appId)) {
    throw "appid not found in manifest.json: $manifestPath"
  }
  return $appId
}

function Invoke-UniAppCliExport([string]$appId, [string]$logPath) {
  $hbuilderRoot = Split-Path -Parent $HBuilderXCli
  $nodeExe = Join-Path $hbuilderRoot 'plugins\node\node.exe'
  $uniCli = Join-Path $hbuilderRoot 'plugins\uniapp-cli\bin\uniapp-cli.js'
  if (-not (Test-Path -LiteralPath $nodeExe)) {
    throw "HBuilderX node not found: $nodeExe"
  }
  if (-not (Test-Path -LiteralPath $uniCli)) {
    throw "uniapp-cli not found: $uniCli"
  }

  $distRoot = Join-Path $ProjectPath 'unpackage\dist\build\app-plus'
  $resourceWww = Join-Path $ProjectPath "unpackage\resources\$appId\www"
  $distService = Join-Path $distRoot 'app-service.js'
  $distView = Join-Path $distRoot 'app-view.js'

  $env:UNI_INPUT_DIR = $ProjectPath
  $env:UNI_OUTPUT_DIR = $distRoot
  $env:UNI_PLATFORM = 'app-plus'
  $env:NODE_ENV = 'production'
  $env:UNI_MINIMIZE = 'true'
  Remove-Item Env:\VUE_CLI_CONTEXT -ErrorAction SilentlyContinue

  $process = Start-Process -FilePath $nodeExe -ArgumentList @($uniCli) -WorkingDirectory (Join-Path $hbuilderRoot 'plugins\uniapp-cli') -NoNewWindow -PassThru -Wait
  "uniapp-cli exit code: $($process.ExitCode)" | Out-File -FilePath $logPath -Encoding utf8 -Append
  if ($process.ExitCode -ne 0) {
    throw "uniapp-cli compile failed, exit=$($process.ExitCode)"
  }
  if (-not (Test-Path -LiteralPath $distService) -and -not (Test-Path -LiteralPath $distView)) {
    throw "compiled app-plus resources missing under: $distRoot"
  }

  New-Item -ItemType Directory -Force -Path $resourceWww | Out-Null
  robocopy $distRoot $resourceWww /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -ge 8) {
    throw "robocopy compiled resources failed, exit=$LASTEXITCODE"
  }
  return $resourceWww
}

function Resolve-SourceWww([string]$appId, [datetime]$publishStartTime) {
  $candidates = @(
    (Join-Path $ProjectPath "unpackage\resources\$appId\www"),
    (Join-Path $ProjectPath "unpackage\cache\wgt\$appId")
  )

  $available = @()
  foreach ($c in $candidates) {
    $appService = Join-Path $c 'app-service.js'
    if (Test-Path -LiteralPath $appService) {
      $item = Get-Item -LiteralPath $appService
      $available += [PSCustomObject]@{
        Root          = $c
        AppService    = $appService
        LastWriteTime = $item.LastWriteTime
      }
    }
  }

  if ($available.Count -eq 0) {
    throw "App resource not found under expected paths for appid=$appId"
  }

  $fresh = $available |
    Where-Object { $_.LastWriteTime -ge $publishStartTime.AddSeconds(-2) } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

  $selected = if ($fresh) {
    $fresh
  }
  else {
    $available | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  }

  if (-not [string]::IsNullOrWhiteSpace($script:VerifyTag)) {
    $match = Get-ChildItem -Path $selected.Root -Recurse -File -ErrorAction SilentlyContinue |
      Select-String -Pattern $script:VerifyTag -SimpleMatch -ErrorAction SilentlyContinue |
      Select-Object -First 1
    if (-not $match) {
      throw "APK_VERIFY_TAG '$script:VerifyTag' not found under $($selected.Root). Export may be stale."
    }
  }

  return $selected.Root
}

function Invoke-CloudPack {
  Ensure-OutputDir 'unpackage\release\apk\cloud'
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $logPath = Join-Path $OutputDir ("pack-$stamp.log")

  $userInfo = & $HBuilderXCli user info 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "HBuilderX user info failed. Please login first. Output: $userInfo"
  }

  $packOutput = & $HBuilderXCli pack --project $ProjectPath --platform android --android.packagename $PackageName --android.androidpacktype 3 2>&1
  $packOutput | Out-File -FilePath $logPath -Encoding utf8

  $downloadUrl = $null
  foreach ($line in $packOutput) {
    if ($line -match 'https?://app\.liuyingyong\.cn/build/download/[A-Za-z0-9\-]+') {
      $downloadUrl = $Matches[0]
      break
    }
  }

  $downloadedApk = $null
  if ($DownloadApk -and $downloadUrl) {
    $apkPath = Join-Path $OutputDir ("app-cloud-$stamp.apk")
    Invoke-WebRequest -Uri $downloadUrl -OutFile $apkPath
    if (Test-Path -LiteralPath $apkPath) {
      $downloadedApk = $apkPath
    }
  }

  $status = if (($packOutput -join "`n") -match '打包成功') { 'success' } else { 'failed' }
  return [PSCustomObject]@{
    status              = $status
    mode_used           = 'cloud'
    pack_log_path       = $logPath
    download_url        = $downloadUrl
    downloaded_apk_path = $downloadedApk
    local_apk_path      = $null
  }
}

function Find-OfflineProjectFromExtracted {
  if (-not (Test-Path -LiteralPath $OfflineSdkExtractDir)) { return $null }
  $match = Get-ChildItem -Path $OfflineSdkExtractDir -Recurse -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -eq 'HBuilder-Integrate-AS' } |
  Select-Object -First 1
  if ($match) { return $match.FullName }
  return $null
}

function Ensure-OfflineProjectPath {
  if (-not [string]::IsNullOrWhiteSpace($OfflineProjectPath) -and (Test-Path -LiteralPath $OfflineProjectPath)) {
    return $OfflineProjectPath
  }

  $fromExtract = Find-OfflineProjectFromExtracted
  if ($fromExtract) { return $fromExtract }

  if (-not [string]::IsNullOrWhiteSpace($OfflineSdkZipPath) -and (Test-Path -LiteralPath $OfflineSdkZipPath)) {
    New-Item -ItemType Directory -Force -Path $OfflineSdkExtractDir | Out-Null
    Expand-Archive -LiteralPath $OfflineSdkZipPath -DestinationPath $OfflineSdkExtractDir -Force
    $afterExtract = Find-OfflineProjectFromExtracted
    if ($afterExtract) { return $afterExtract }
  }

  throw 'Offline project not found. Provide -OfflineProjectPath or -OfflineSdkZipPath.'
}

function Invoke-LocalPack {
  Ensure-OutputDir 'unpackage\release\apk\local'
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $logPath = Join-Path $OutputDir ("local-pack-$stamp.log")
  $appId = Get-AppIdFromManifest
  $publishStartTime = Get-Date

  try {
    Invoke-UniAppCliExport -appId $appId -logPath $logPath | Out-Null
  }
  catch {
    $_ | Out-File -FilePath $logPath -Encoding utf8 -Append
    return [PSCustomObject]@{
      status              = 'failed'
      mode_used           = 'local'
      pack_log_path       = $logPath
      download_url        = $null
      downloaded_apk_path = $null
      local_apk_path      = $null
    }
  }

  $offlineProject = Ensure-OfflineProjectPath
  $assetsApps = Join-Path $offlineProject 'simpleDemo\src\main\assets\apps'
  $controlXml = Join-Path $offlineProject 'simpleDemo\src\main\assets\data\dcloud_control.xml'
  $localProperties = Join-Path $offlineProject 'local.properties'
  $sourceWww = Resolve-SourceWww -appId $appId -publishStartTime $publishStartTime

  if (Test-Path -LiteralPath $assetsApps) {
    Get-ChildItem -LiteralPath $assetsApps -Directory -Filter '__UNI__*' |
      Where-Object { $_.Name -ne $appId } |
      Remove-Item -Recurse -Force
  }
  if (Test-Path (Join-Path $assetsApps $appId)) {
    Remove-Item -Recurse -Force (Join-Path $assetsApps $appId)
  }
  $targetWww = Join-Path $assetsApps "$appId\www"
  New-Item -ItemType Directory -Force -Path $targetWww | Out-Null
  Copy-Item -Recurse -Force "$sourceWww\*" $targetWww

  @"
<hbuilder>
<apps>
    <app appid="$appId" appver=""/>
</apps>
</hbuilder>
"@ | Set-Content -Path $controlXml -Encoding utf8

  @"
sdk.dir=$($AndroidSdkDir -replace '\\','\\\\')
"@ | Set-Content -Path $localProperties -Encoding ascii

  Push-Location $offlineProject
  $gradleOutput = cmd /c gradlew.bat :simpleDemo:assembleRelease --stacktrace 2>&1
  Pop-Location
  $gradleOutput | Out-File -FilePath $logPath -Encoding utf8 -Append

  $localApk = Join-Path $offlineProject 'simpleDemo\build\outputs\apk\release\simpleDemo-release.apk'
  $status = if (Test-Path -LiteralPath $localApk) { 'success' } else { 'failed' }
  return [PSCustomObject]@{
    status              = $status
    mode_used           = 'local'
    pack_log_path       = $logPath
    download_url        = $null
    downloaded_apk_path = $null
    local_apk_path      = $(if ($status -eq 'success') { $localApk } else { $null })
  }
}

Ensure-BaseValidation
$script:VerifyTag = Resolve-VerifyTag

if ($Mode -eq 'local') {
  $r = Invoke-LocalPack
  Write-ResultAndExit -status $r.status -modeUsed $r.mode_used -packLogPath $r.pack_log_path -downloadUrl $r.download_url -downloadedApkPath $r.downloaded_apk_path -localApkPath $r.local_apk_path
}

if ($Mode -eq 'cloud') {
  $r = Invoke-CloudPack
  Write-ResultAndExit -status $r.status -modeUsed $r.mode_used -packLogPath $r.pack_log_path -downloadUrl $r.download_url -downloadedApkPath $r.downloaded_apk_path -localApkPath $r.local_apk_path
}

# auto
try {
  $localResult = Invoke-LocalPack
  if ($localResult.status -eq 'success') {
    Write-ResultAndExit -status $localResult.status -modeUsed $localResult.mode_used -packLogPath $localResult.pack_log_path -downloadUrl $localResult.download_url -downloadedApkPath $localResult.downloaded_apk_path -localApkPath $localResult.local_apk_path
  }
}
catch {
  # fallback to cloud below
}

$cloudResult = Invoke-CloudPack
Write-ResultAndExit -status $cloudResult.status -modeUsed $cloudResult.mode_used -packLogPath $cloudResult.pack_log_path -downloadUrl $cloudResult.download_url -downloadedApkPath $cloudResult.downloaded_apk_path -localApkPath $cloudResult.local_apk_path
