param(
  [Parameter(Mandatory = $true)][string]$Prompt,
  [string]$ProjectRoot = "",
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
  $jsonPath = Join-Path $script:ProjectRoot "config\spaceConfig.json"
  if (Test-Path $jsonPath) {
    return Get-Content -Raw -LiteralPath $jsonPath | ConvertFrom-Json
  }

  $jsPath = Join-Path $script:ProjectRoot "config\localDebug.js"
  if (!(Test-Path $jsPath)) {
    return $null
  }

  $text = Get-Content -Raw -LiteralPath $jsPath
  $httpMatch = [regex]::Match($text, 'http:\s*(\d+)')
  $wsMatch = [regex]::Match($text, 'ws:\s*(\d+)')
  $phoneMatch = [regex]::Match($text, 'phone:\s*"([^"]+)"')
  $passwordMatch = [regex]::Match($text, 'password:\s*"([^"]+)"')
  $trainingMatch = [regex]::Match($text, 'LOCAL_TRAINING_DEVICE_ID\s*=\s*"([^"]+)"')

  return [PSCustomObject]@{
    spaceName = $script:SpaceName
    projectRoot = $script:ProjectRoot
    packageName = $PackageName
    deviceId = ""
    backendMode = "direct"
    directHost = "192.168.200.128"
    forwardHost = "192.168.31.23"
    httpPort = $(if ($httpMatch.Success) { [int]$httpMatch.Groups[1].Value } else { 0 })
    wsPort = $(if ($wsMatch.Success) { [int]$wsMatch.Groups[1].Value } else { 0 })
    loginPrefill = @{
      enabled = $true
      loginMode = "password"
      phone = $(if ($phoneMatch.Success) { $phoneMatch.Groups[1].Value } else { "" })
      password = $(if ($passwordMatch.Success) { $passwordMatch.Groups[1].Value } else { "" })
      agreed = $true
    }
    trainingDeviceId = $(if ($trainingMatch.Success) { $trainingMatch.Groups[1].Value } else { "" })
  }
}

$script:SpaceConfig = Read-SpaceConfig

function Read-LocalDebugConfig {
  return @{
    HttpPort = [string]$script:SpaceConfig.httpPort
    Phone = [string]$script:SpaceConfig.loginPrefill.phone
  }
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
    $port = [string]$script:SpaceConfig.httpPort
  }
  if ([string]::IsNullOrWhiteSpace($port)) {
    throw "http port is required"
  }
  $backendHost = if ([string]$script:SpaceConfig.backendMode -eq "forward") { [string]$script:SpaceConfig.forwardHost } else { [string]$script:SpaceConfig.directHost }
  if ([string]::IsNullOrWhiteSpace($backendHost)) {
    $backendHost = "192.168.200.128"
  }
  return "http://${backendHost}:$port"
}

function Resolve-RemoteInstanceId {
  if ($script:SpaceConfig -and ![string]::IsNullOrWhiteSpace([string]$script:SpaceConfig.spaceName)) {
    return [string]$script:SpaceConfig.spaceName
  }
  return $script:SpaceName
}

function Resolve-LatestFrontendChatSession {
  $instanceId = Resolve-RemoteInstanceId
  if ([string]::IsNullOrWhiteSpace($instanceId)) {
    return $null
  }
  $sshKey = "C:\Users\zhangrjzrj\.ssh\app4_vmware_cdp_ed25519"
  if (!(Test-Path $sshKey)) {
    return $null
  }
  $remoteLog = "/home/zhangrjzrj/hanhan-runtime/ai_backend/instances/$instanceId/logs/client-av-debug-$(Get-Date -Format 'yyyy-MM-dd').log"
  $remoteCommand = "tail -n 2000 '$remoteLog' 2>/dev/null | grep 'debug_chat_command_poll_result' | tail -n 1"
  $line = & ssh -i $sshKey zhangrjzrj@192.168.200.128 $remoteCommand
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($line)) {
    return $null
  }
  try {
    $record = $line | ConvertFrom-Json
    $event = $record.event
    $member = [string]$event.member_id
    if ([string]::IsNullOrWhiteSpace($member)) {
      $member = [string]$record.id
    }
    $session = [string]$event.session_id
    if ([string]::IsNullOrWhiteSpace($session)) {
      $session = [string]$record.session_id
    }
    if ([string]::IsNullOrWhiteSpace($member) -or [string]::IsNullOrWhiteSpace($session)) {
      return $null
    }
    return [PSCustomObject]@{
      MemberId = $member
      SessionId = $session
      Source = $remoteLog
    }
  } catch {
    return $null
  }
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

function Get-AdbScreenSize {
  $raw = (& adb @script:AdbPrefix shell wm size) -join "`n"
  $match = [regex]::Match($raw, 'Physical size:\s*(\d+)x(\d+)')
  if (-not $match.Success) {
    throw "failed to read adb screen size: $raw"
  }
  return [PSCustomObject]@{
    Width = [int]$match.Groups[1].Value
    Height = [int]$match.Groups[2].Value
  }
}

function Convert-ReferencePointToScreen {
  param(
    [Parameter(Mandatory = $true)][int]$X,
    [Parameter(Mandatory = $true)][int]$Y,
    [int]$ReferenceWidth = 1080,
    [int]$ReferenceHeight = 1920
  )
  $size = Get-AdbScreenSize
  $scaledX = [Math]::Round($X * $size.Width / $ReferenceWidth)
  $scaledY = [Math]::Round($Y * $size.Height / $ReferenceHeight)
  return [PSCustomObject]@{
    X = [int][Math]::Max(0, [Math]::Min($size.Width - 1, $scaledX))
    Y = [int][Math]::Max(0, [Math]::Min($size.Height - 1, $scaledY))
    Reference = "${ReferenceWidth}x${ReferenceHeight}"
    Screen = "$($size.Width)x$($size.Height)"
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
  $commandMemberId = $ResolvedMemberId
  $commandSessionId = $SessionId
  $resolvedSession = $null
  if ([string]::IsNullOrWhiteSpace($commandSessionId) -and $commandMemberId -eq [string]$config.Phone) {
    $resolvedSession = Resolve-LatestFrontendChatSession
    if ($null -eq $resolvedSession) {
      throw "cannot resolve active frontend chat session; pass -MemberId and -SessionId to avoid broadcasting a default debug command"
    }
    $commandMemberId = $resolvedSession.MemberId
    $commandSessionId = $resolvedSession.SessionId
  }
  $body = @{
    member_id = $commandMemberId
    session_id = $commandSessionId
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
      if ($poll -and $poll.result -and $poll.result.PSObject.Properties.Name -contains "result" -and $null -ne $poll.result.result) {
        $reported = $poll.result.result
        break
      }
    } catch {}
  }
  return [PSCustomObject]@{
    command_id = $commandId
    target_member_id = $commandMemberId
    target_session_id = $commandSessionId
    reported = $reported
  }
}

function Invoke-AdbFallbackSend {
  $beforePath = Dump-Ui -Name ("duomilu-before-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
  [xml]$beforeXml = Get-Content -Raw -LiteralPath $beforePath -Encoding UTF8
  $promptNode = Get-PromptNode -Xml $beforeXml
  if ($null -eq $promptNode) {
    # WORKAROUND: Some WebView dumps omit the bottom EditText node even when the
    # real chat composer is visible. Fall back to a scaled reference point in
    # the bottom composer area until the frontend exposes a stable node.
    $promptCenter = Convert-ReferencePointToScreen -X 620 -Y 1755
  } else {
    $promptCenter = Get-BoundsCenter -Node $promptNode
  }
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
    if ($null -eq $sendNode) {
      # WORKAROUND: Current chat-page dumps may hide the send button subtree after
      # text paste. Use a scaled right-edge send-region reference until the
      # frontend exposes a stable node for automation.
      $sendCenter = Convert-ReferencePointToScreen -X 1000 -Y 1755
    } else {
      $sendCenter = Get-BoundsCenter -Node $sendNode
    }
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
  project_root = $script:ProjectRoot
  space = $script:SpaceName
  device_id = $DeviceId
  package_name = $PackageName
  http_base = $resolvedHttpBase
  member_id = $MemberId
  session_id = $SessionId
  target_member_id = $(if ($commandResult) { $commandResult.target_member_id } else { "" })
  target_session_id = $(if ($commandResult) { $commandResult.target_session_id } else { "" })
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
