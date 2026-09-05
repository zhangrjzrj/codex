param(
  [Parameter(Mandatory = $true)][string]$Prompt,
  [string]$ProjectRoot = "",
  [string]$DeviceId = "",
  [string]$PackageName = "com.chaoweisuanli.duomilu",
  [string]$EvidenceDir = "",
  [int]$AfterSendWaitSeconds = 3
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
  $ProjectRoot = (Get-Location).Path
}

$script:ProjectRoot = $ProjectRoot
$script:SpaceName = Split-Path -Leaf $script:ProjectRoot
$script:AdbPrefix = @()

function Step($msg) {
  Write-Host ""
  Write-Host "==> $msg" -ForegroundColor Cyan
}

function Read-SpaceConfig {
  $spaceConfigPath = Join-Path $script:ProjectRoot "config\spaces\$script:SpaceName.json"
  if (!(Test-Path $spaceConfigPath)) {
    throw "missing space config: $spaceConfigPath"
  }
  return Get-Content -Raw -LiteralPath $spaceConfigPath | ConvertFrom-Json
}

function Resolve-DefaultDeviceId {
  if ($script:SpaceConfig -and ![string]::IsNullOrWhiteSpace([string]$script:SpaceConfig.deviceId)) {
    return [string]$script:SpaceConfig.deviceId
  }
  switch ($script:SpaceName) {
    "app1" { return "emulator-5554" }
    "app2" { return "emulator-5556" }
    "app3" { return "emulator-5558" }
    "app4" { return "emulator-5560" }
    "app5" { return "emulator-5562" }
    default { throw "DeviceId is required for unknown space: $script:SpaceName" }
  }
}

function Invoke-Adb {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
  & adb @script:AdbPrefix @Args
}

function Ensure-AdbOk {
  $devices = & adb devices
  if ($LASTEXITCODE -ne 0) {
    throw "adb devices failed"
  }
  $target = $devices | Where-Object { $_ -match ("^{0}\s+device$" -f [regex]::Escape($DeviceId)) }
  if (-not $target) {
    throw "target adb device not ready: $DeviceId"
  }
}

function Assert-AppInForeground {
  param([string]$Pkg)
  $focus = Invoke-Adb shell dumpsys window | Select-String -Pattern "mCurrentFocus|mFocusedApp"
  if ($LASTEXITCODE -ne 0) {
    throw "dumpsys window failed"
  }
  $text = ($focus | ForEach-Object { $_.Line }) -join "`n"
  if ($text -notmatch [regex]::Escape($Pkg)) {
    throw "target app is not foreground: $Pkg. focus=$text"
  }
  return $text
}

function Dump-Ui {
  param([string]$Name)
  New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
  $remote = "/sdcard/$Name.xml"
  $local = Join-Path $EvidenceDir "$Name.xml"
  Invoke-Adb shell uiautomator dump $remote | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "uiautomator dump failed: $Name"
  }
  Invoke-Adb pull $remote $local | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "adb pull dump failed: $Name"
  }
  return $local
}

function Invoke-DeviceDebugSend {
  $encoded = [uri]::EscapeDataString($Prompt)
  $commandId = [uri]::EscapeDataString(("cmd-{0}-{1}" -f (Get-Date -Format 'yyyyMMddHHmmssfff'), ([guid]::NewGuid().ToString('N').Substring(0, 8))))
  $deepLink = "duomilu://debug-chat?action=send_text&text=$encoded&command_id=$commandId"
  $entryActivity = "$PackageName/io.dcloud.PandoraEntry"
  $shellCommand = "am start -W -a android.intent.action.VIEW -d '$deepLink' -n $entryActivity"
  & adb @script:AdbPrefix "shell" $shellCommand | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "adb debug deep link failed"
  }
  return $deepLink
}

$script:SpaceConfig = Read-SpaceConfig
if ([string]::IsNullOrWhiteSpace($DeviceId)) {
  $DeviceId = Resolve-DefaultDeviceId
}
if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
  $EvidenceDir = Join-Path $script:ProjectRoot ".local-artifacts\runtime-evidence\duomilu-send-prompt"
}
$script:AdbPrefix = @("-s", $DeviceId)

Ensure-AdbOk
$focusText = Assert-AppInForeground -Pkg $PackageName
Step "Dump UI before device debug command"
$beforePath = Dump-Ui -Name ("duomilu-before-" + (Get-Date -Format "yyyyMMdd-HHmmss"))

Step "Send device-directed debug deep link"
$deepLink = Invoke-DeviceDebugSend

Start-Sleep -Seconds $AfterSendWaitSeconds
Step "Dump UI after send"
$afterPath = Dump-Ui -Name ("duomilu-after-" + (Get-Date -Format "yyyyMMdd-HHmmss"))

[PSCustomObject]@{
  status = "sent"
  project_root = $script:ProjectRoot
  space = $script:SpaceName
  device_id = $DeviceId
  package_name = $PackageName
  submit_mode = "adb_deeplink_client_api"
  prompt = $Prompt
  used_prompt = $Prompt
  deep_link = $deepLink
  focus = $focusText
  before_dump = $beforePath
  after_dump = $afterPath
} | ConvertTo-Json -Depth 6
