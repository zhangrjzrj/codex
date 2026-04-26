param(
  [Parameter(Mandatory=$true)][string]$ProjectPath,
  [Parameter(Mandatory=$true)][string]$PackageName,
  [ValidateSet('auto','local','cloud')][string]$Mode = 'local',
  [string]$HBuilderXCli = 'D:\hanhan\HBuilderX\cli.exe',
  [string]$OutputDir = '',
  [switch]$DownloadApk,
  [string]$OfflineSdkZipPath = '',
  [string]$OfflineSdkExtractDir = 'D:\hanhan\offline-pack\android-sdk',
  [string]$OfflineProjectPath = '',
  [string]$AndroidSdkDir = 'D:\AndroidSDK'
)

$ErrorActionPreference = 'Stop'

function Ensure-BaseValidation {
  if (-not (Test-Path -LiteralPath $HBuilderXCli)) {
    throw "HBuilderX cli not found: $HBuilderXCli"
  }
  if (-not (Test-Path -LiteralPath $ProjectPath)) {
    throw "Project path not found: $ProjectPath"
  }
  if (-not (Test-Path -LiteralPath (Join-Path $ProjectPath 'manifest.json'))) {
    throw "manifest.json not found under project: $ProjectPath"
  }
}

function Ensure-OutputDir([string]$DefaultSubdir) {
  if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $script:OutputDir = Join-Path $ProjectPath $DefaultSubdir
  }
  New-Item -ItemType Directory -Force -Path $script:OutputDir | Out-Null
}

function Write-ResultAndExit([string]$status, [string]$modeUsed, [string]$packLogPath, [string]$downloadUrl, [string]$downloadedApkPath, [string]$localApkPath) {
  $result = [PSCustomObject]@{
    status = $status
    mode_used = $modeUsed
    pack_log_path = $packLogPath
    download_url = $downloadUrl
    downloaded_apk_path = $downloadedApkPath
    local_apk_path = $localApkPath
  }
  $result | ConvertTo-Json -Depth 5
  if ($status -ne 'success') { exit 2 }
  exit 0
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
    status = $status
    mode_used = 'cloud'
    pack_log_path = $logPath
    download_url = $downloadUrl
    downloaded_apk_path = $downloadedApk
    local_apk_path = $null
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

  $publishOutput = & $HBuilderXCli publish app-android --type appResource --project $ProjectPath 2>&1
  $publishOutput | Out-File -FilePath $logPath -Encoding utf8
  if ($LASTEXITCODE -ne 0) {
    return [PSCustomObject]@{
      status = 'failed'; mode_used='local'; pack_log_path=$logPath; download_url=$null; downloaded_apk_path=$null; local_apk_path=$null
    }
  }

  $offlineProject = Ensure-OfflineProjectPath
  $assetsApps = Join-Path $offlineProject 'simpleDemo\src\main\assets\apps'
  $controlXml = Join-Path $offlineProject 'simpleDemo\src\main\assets\data\dcloud_control.xml'
  $localProperties = Join-Path $offlineProject 'local.properties'
  $sourceWww = Join-Path $ProjectPath 'unpackage\resources\__UNI__B41F254\www'

  if (-not (Test-Path -LiteralPath $sourceWww)) {
    throw "App resource not found: $sourceWww"
  }

  if (Test-Path (Join-Path $assetsApps '__UNI__A')) {
    Remove-Item -Recurse -Force (Join-Path $assetsApps '__UNI__A')
  }
  if (Test-Path (Join-Path $assetsApps '__UNI__B41F254')) {
    Remove-Item -Recurse -Force (Join-Path $assetsApps '__UNI__B41F254')
  }
  New-Item -ItemType Directory -Force -Path (Join-Path $assetsApps '__UNI__B41F254') | Out-Null
  Copy-Item -Recurse -Force $sourceWww (Join-Path $assetsApps '__UNI__B41F254\www')

  @"
<hbuilder>
<apps>
    <app appid="__UNI__B41F254" appver=""/>
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
    status = $status
    mode_used = 'local'
    pack_log_path = $logPath
    download_url = $null
    downloaded_apk_path = $null
    local_apk_path = $(if ($status -eq 'success') { $localApk } else { $null })
  }
}

Ensure-BaseValidation

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
} catch {
  # fallback to cloud below
}

$cloudResult = Invoke-CloudPack
Write-ResultAndExit -status $cloudResult.status -modeUsed $cloudResult.mode_used -packLogPath $cloudResult.pack_log_path -downloadUrl $cloudResult.download_url -downloadedApkPath $cloudResult.downloaded_apk_path -localApkPath $cloudResult.local_apk_path
