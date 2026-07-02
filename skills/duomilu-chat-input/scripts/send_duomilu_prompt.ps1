param(
  [Parameter(Mandatory = $true)][string]$Prompt,
  [string]$DeviceId = "",
  [string]$MemberId = "",
  [string]$SessionId = "",
  [string]$HttpBase = "",
  [string]$PackageName = "com.chaoweisuanli.duomilu",
  [string]$EvidenceDir = "",
  [int]$AfterSendWaitSeconds = 3,
  [int]$CommandWaitSeconds = 15,
  [switch]$AllowAdbFallback,
  [string]$AsciiFallbackPrompt = "",
  [switch]$PressEnterInsteadOfTapSend
)

$ErrorActionPreference = "Stop"

$script:ProjectRoot = Split-Path -Parent $PSScriptRoot
$script:SpaceName = Split-Path -Leaf $script:ProjectRoot
$script:AdbPrefix = @()

function Step($msg) {
  Write-Host ""
  Write-Host "==> $msg" -ForegroundColor Cyan
}

function Read-LocalDebugConfig {
  $path = Join-Path $script:ProjectRoot "config\localDebug.js"
  if (!(Test-Path $path)) {
    return @{
      HttpPort = "";
      Phone = "";
    }
  }
  $text = Get-Content -Raw -LiteralPath $path
  $httpMatch = [regex]::Match($text, 'http:\s*(\d+)')
  $phoneMatch = [regex]::Match($text, 'phone:\s*"([^"]+)"')
  return @{
    HttpPort = $(if ($httpMatch.Success) { $httpMatch.Groups[1].Value } else { "" })
    Phone = $(if ($phoneMatch.Success) { $phoneMatch.Groups[1].Value } else { "" })
  }
}

function Resolve-DefaultDeviceId {
  switch ($script:SpaceName) {
    "app1" { return "emulator-5554" }
    "app2" { return "emulator-5556" }
    "app3" { return "emulator-5558" }
    "app4" { return "emulator-5560" }
    "app5" { return "emulator-5560" }
    default { return "emulator-5554" }
  }
}

function Resolve-HttpBase {
  param($Config)
  if (![string]::IsNullOrWhiteSpace($HttpBase)) {
    return $HttpBase.TrimEnd("/")
  }
  $port = [string]$Config.HttpPort
  if ([string]::IsNullOrWhiteSpace($port)) {
    switch ($script:SpaceName) {
      "app1" { $port = "8784" }
      "app2" { $port = "8785" }
      "app3" { $port = "8786" }
      "app4" { $port = "8787" }
      "app5" { $port = "8788" }
      default { $port = "8787" }
    }
  }
  return "http://192.168.200.128:$port"
}

function Invoke-Adb {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
  & adb @script:AdbPrefix @Args
}

function Ensure-AdbOk {
  $devices = & adb devices
  if ($LASTEXITCODE -ne 0) { throw "adb devices failed" }
  if (![string]::IsNullOrWhiteSpace($DeviceId)) {
    $target = $devices | Where-Object { $_ -match ("^{0}\s+device$" -f [regex]::Escape($DeviceId)) }
    if (-not $target) { throw "target adb device not ready: $DeviceId" }
    return
  }
  $ready = $devices | Where-Object { $_ -match "\tdevice$" }
  if (-not $ready) { throw "no adb device in device state" }
}

function Assert-AppInForeground {
  param([string]$Pkg)
  $focus = Invoke-Adb shell dumpsys window | Select-String -Pattern "mCurrentFocus|mFocusedApp"
  if ($LASTEXITCODE -ne 0) { throw "dumpsys window failed" }
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
  if ($LASTEXITCODE -ne 0) { throw "uiautomator dump failed: $Name" }
  Invoke-Adb pull $remote $local | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "adb pull dump failed: $Name" }
  return $local
}

function Get-NodeByResourceId {
  param([xml]$Xml, [string]$ResourceId)
  $nodes = $Xml.SelectNodes("//*[@resource-id='$ResourceId']")
  if ($nodes.Count -eq 0) { return $null }
  return $nodes.Item(0)
}

function Get-BoundsCenter {
  param($Node)
  if ($null -eq $Node) { throw "node is null" }
  $bounds = [string]$Node.bounds
  $m = [regex]::Match($bounds, "\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
  if (-not $m.Success) { throw "invalid bounds: $bounds" }
  $left = [int]$m.Groups[1].Value
  $top = [int]$m.Groups[2].Value
  $right = [int]$m.Groups[3].Value
  $bottom = [int]$m.Groups[4].Value
  return [PSCustomObject]@{
    X = [int](($left + $right) / 2)
    Y = [int](($top + $bottom) / 2)
    Bounds = $bounds
    Width = $right - $left
    Height = $bottom - $top
  }
}

function Get-PromptNode {
  param([xml]$Xml)
  $node = Get-NodeByResourceId -Xml $Xml -ResourceId "prompt"
  if ($null -ne $node) { return $node }
  $nodes = $Xml.SelectNodes("//node[@class='android.widget.EditText' and @enabled='true']")
  foreach ($candidate in $nodes) {
    $center = Get-BoundsCenter -Node $candidate
    if ($center.Y -gt 1500) {
      return $candidate
    }
  }
  return $null
}

function Get-SendNode {
  param([xml]$Xml)
  $node = Get-NodeByResourceId -Xml $Xml -ResourceId "send"
  if ($null -ne $node) { return $node }
  foreach ($candidate in $Xml.SelectNodes("//node[@enabled='true']")) {
    if ([string]$candidate.text -like "*发送*") {
      return $candidate
    }
  }
  return $null
}

function Convert-ToAdbText {
  param([string]$Text)
  if ($Text -match "[^\x20-\x7E]") {
    if ([string]::IsNullOrWhiteSpace($AsciiFallbackPrompt)) {
      throw "adb shell input text only supports ASCII reliably. Provide -AsciiFallbackPrompt for non-ASCII prompts."
    }
    $Text = $AsciiFallbackPrompt
  }
  $escaped = $Text.Replace(" ", "%s").Replace("&", "`&").Replace("|", "`|").Replace("<", "`<").Replace(">", "`>").Replace(";", "`;")
  return [PSCustomObject]@{ Original = $Prompt; Used = $Text; Escaped = $escaped }
}

function Invoke-AdbInputText {
  param([string]$Text)
  Set-Clipboard -Value $Text
  Invoke-Adb shell input keyevent 279
  if ($LASTEXITCODE -eq 0) { return $Text }
  $converted = Convert-ToAdbText -Text $Text
  Invoke-Adb shell input text $converted.Escaped
  if ($LASTEXITCODE -ne 0) { throw "adb text input and paste both failed" }
  return $converted.Used
}

function Invoke-JsonPost {
  param([string]$Url, [hashtable]$Body)
  $json = $Body | ConvertTo-Json -Depth 8
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
  return Invoke-RestMethod -Method Post -Uri $Url -ContentType "application/json; charset=utf-8" -Body $bytes -TimeoutSec 10
}

function Invoke-FrontendDebugCommand {
  param([string]$BaseUrl, [string]$ResolvedMemberId)
  $url = "$BaseUrl/webapi/debug/chat-command"
  $body = @{
    member_id = $ResolvedMemberId
    session_id = $SessionId
    type = "send_text"
    text = $Prompt
  }
  $res = Invoke-JsonPost -Url $url -Body $body
  if ([int]$res.code -ne 200 -or -not $res.result -or -not $res.result.id) {
    throw "debug command enqueue failed: $($res | ConvertTo-Json -Depth 6)"
  }
  $commandId = [string]$res.result.id
  $deadline = (Get-Date).AddSeconds($CommandWaitSeconds)
  $reported = $null
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 800
    try {
      $poll = Invoke-RestMethod -Uri "$url?command_id=$commandId" -TimeoutSec 5
      $reported = $poll.result.result
      if ($reported) {
        break
      }
    } catch {}
  }
  return [PSCustomObject]@{
    command_id = $commandId
    reported = $reported
  }
}

function Invoke-AdbFallbackSend {
  $beforePath = Dump-Ui -Name ("duomilu-before-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
  [xml]$beforeXml = Get-Content -Raw -LiteralPath $beforePath -Encoding UTF8
  $promptNode = Get-PromptNode -Xml $beforeXml
  if ($null -eq $promptNode) { throw "prompt input not found in UI dump: $beforePath" }
  $promptCenter = Get-BoundsCenter -Node $promptNode
  Invoke-Adb shell input tap $promptCenter.X $promptCenter.Y
  if ($LASTEXITCODE -ne 0) { throw "tap prompt failed" }
  Start-Sleep -Milliseconds 400
  $usedPrompt = Invoke-AdbInputText -Text $Prompt
  Start-Sleep -Milliseconds 300
  if ($PressEnterInsteadOfTapSend) {
    Invoke-Adb shell input keyevent 66
    if ($LASTEXITCODE -ne 0) { throw "send keyevent failed" }
  } else {
    $midPath = Dump-Ui -Name ("duomilu-before-send-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    [xml]$midXml = Get-Content -Raw -LiteralPath $midPath -Encoding UTF8
    $sendNode = Get-SendNode -Xml $midXml
    if ($null -eq $sendNode) { throw "send button not found in UI dump: $midPath" }
    $sendCenter = Get-BoundsCenter -Node $sendNode
    Invoke-Adb shell input tap $sendCenter.X $sendCenter.Y
    if ($LASTEXITCODE -ne 0) { throw "tap send failed" }
  }
  return [PSCustomObject]@{
    used_prompt = $usedPrompt
    before_dump = $beforePath
  }
}

$config = Read-LocalDebugConfig
if ([string]::IsNullOrWhiteSpace($DeviceId)) {
  $DeviceId = Resolve-DefaultDeviceId
}
if ([string]::IsNullOrWhiteSpace($MemberId)) {
  $MemberId = [string]$config.Phone
}
if ([string]::IsNullOrWhiteSpace($MemberId)) {
  throw "member id is required; pass -MemberId or configure LOCAL_LOGIN_PREFILL.phone"
}
if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
  $EvidenceDir = Join-Path $script:ProjectRoot ".local-artifacts\runtime-evidence\duomilu-send-prompt"
}
$resolvedHttpBase = Resolve-HttpBase -Config $config
$script:AdbPrefix = @("-s", $DeviceId)

Ensure-AdbOk
$focusText = Assert-AppInForeground -Pkg $PackageName
Step "Dump UI before frontend debug command"
$beforePath = Dump-Ui -Name ("duomilu-before-" + (Get-Date -Format "yyyyMMdd-HHmmss"))

$submitMode = "frontend_debug_command"
$commandResult = $null
$fallbackResult = $null
$errorText = ""
try {
  Step "Post frontend debug command"
  $commandResult = Invoke-FrontendDebugCommand -BaseUrl $resolvedHttpBase -ResolvedMemberId $MemberId
  if (-not $commandResult.reported) {
    throw "frontend command was not reported within ${CommandWaitSeconds}s"
  }
} catch {
  $errorText = $_.Exception.Message
  if (-not $AllowAdbFallback) {
    throw
  }
  Step "Frontend debug command failed; fallback to ADB input"
  $submitMode = "adb_fallback"
  $fallbackResult = Invoke-AdbFallbackSend
}

Start-Sleep -Seconds $AfterSendWaitSeconds
Step "Dump UI after send"
$afterPath = Dump-Ui -Name ("duomilu-after-" + (Get-Date -Format "yyyyMMdd-HHmmss"))

[PSCustomObject]@{
  status = "sent"
  space = $script:SpaceName
  device_id = $DeviceId
  package_name = $PackageName
  http_base = $resolvedHttpBase
  member_id = $MemberId
  session_id = $SessionId
  submit_mode = $submitMode
  command_id = $(if ($commandResult) { $commandResult.command_id } else { "" })
  command_report = $(if ($commandResult) { $commandResult.reported } else { $null })
  frontend_error = $errorText
  prompt = $Prompt
  used_prompt = $(if ($fallbackResult) { $fallbackResult.used_prompt } else { $Prompt })
  focus = $focusText
  before_dump = $beforePath
  after_dump = $afterPath
} | ConvertTo-Json -Depth 8
