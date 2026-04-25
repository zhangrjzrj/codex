param(
  [Parameter(Mandatory=$true)][string]$ProjectPath,
  [Parameter(Mandatory=$true)][string]$PackageName,
  [string]$HBuilderXCli = 'D:\hanhan\HBuilderX\cli.exe',
  [string]$OutputDir = '',
  [switch]$DownloadApk
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $HBuilderXCli)) {
  throw "HBuilderX cli not found: $HBuilderXCli"
}
if (-not (Test-Path -LiteralPath $ProjectPath)) {
  throw "Project path not found: $ProjectPath"
}
if (-not (Test-Path -LiteralPath (Join-Path $ProjectPath 'manifest.json'))) {
  throw "manifest.json not found under project: $ProjectPath"
}

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $OutputDir = Join-Path $ProjectPath 'unpackage\release\apk\cloud'
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logPath = Join-Path $OutputDir ("pack-$stamp.log")

# Ensure login state
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

$result = [PSCustomObject]@{
  status = $status
  pack_log_path = $logPath
  download_url = $downloadUrl
  downloaded_apk_path = $downloadedApk
}

$result | ConvertTo-Json -Depth 5
if ($status -ne 'success') {
  exit 2
}
