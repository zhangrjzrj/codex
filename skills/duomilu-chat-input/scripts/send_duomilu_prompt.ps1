param(
  [Parameter(Mandatory = $true)][string]$Prompt,
  [string]$DeviceId = "",
  [string]$PackageName = "com.chaoweisuanli.duomilu",
  [string]$EvidenceDir = ".local-artifacts\runtime-evidence\duomilu-send-prompt",
  [int]$AfterSendWaitSeconds = 3,
  [string]$AsciiFallbackPrompt = "",
  [switch]$PressEnterInsteadOfTapSend
)

$ErrorActionPreference = "Stop"
$script:AdbPrefix = @()
$script:ClipboardSnapshot = $null
$script:ClipboardCaptured = $false
$script:ClipboardGuardId = [guid]::NewGuid().ToString("N")
$script:ClipboardGuardDir = Join-Path $env:TEMP "codex-clipboard-guard"
$script:ClipboardGuardSnapshotPath = Join-Path $script:ClipboardGuardDir ($script:ClipboardGuardId + ".txt")
$script:ClipboardGuardCancelPath = Join-Path $script:ClipboardGuardDir ($script:ClipboardGuardId + ".cancel")
$script:ClipboardGuardProc = $null
if (-not [string]::IsNullOrWhiteSpace($DeviceId)) {
  $script:AdbPrefix = @("-s", $DeviceId)
}

function Step($msg) {
  Write-Host ""
  Write-Host "==> $msg" -ForegroundColor Cyan
}

function Invoke-Adb {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
  )
  & adb @script:AdbPrefix @Args
}

function Ensure-AdbOk {
  $devices = & adb devices
  if ($LASTEXITCODE -ne 0) { throw "adb devices failed" }
  if (-not [string]::IsNullOrWhiteSpace($DeviceId)) {
    $target = $devices | Where-Object { $_ -match ("^{0}\s+device$" -f [regex]::Escape($DeviceId)) }
    if (-not $target) { throw "target adb device not ready: $DeviceId" }
    return
  }
  $ready = $devices | Where-Object { $_ -match "\tdevice$" }
  if (-not $ready) { throw "no adb device in device state" }
  if (($ready | Measure-Object).Count -gt 1) {
    throw "multiple adb devices detected; pass -DeviceId explicitly"
  }
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
  $dumpOk = $false
  for ($attempt = 1; $attempt -le 3; $attempt++) {
    Invoke-Adb shell rm -f $remote | Out-Null
    Invoke-Adb shell uiautomator dump $remote | Out-Null
    if ($LASTEXITCODE -eq 0) {
      Invoke-Adb pull $remote $local | Out-Null
      if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $local)) {
        $dumpOk = $true
        break
      }
    }
    Start-Sleep -Milliseconds 500
  }
  if (-not $dumpOk) { throw "uiautomator dump/pull failed after retries: $Name" }
  return $local
}

function Get-NodeByResourceId {
  param(
    [xml]$Xml,
    [string]$ResourceId
  )
  $nodes = $Xml.SelectNodes("//*[@resource-id='$ResourceId']")
  if ($nodes.Count -eq 0) { return $null }
  return $nodes.Item(0)
}

function Get-DumpPageMarkers {
  param([xml]$Xml)
  $markers = @()
  foreach ($candidate in $Xml.SelectNodes("//node")) {
    $text = [string]$candidate.text
    if ($text -like "pages/home/*") {
      $markers += $text
    }
  }
  return $markers
}

function Test-IsChatPage {
  param([xml]$Xml)
  foreach ($marker in (Get-DumpPageMarkers -Xml $Xml)) {
    if ($marker -like "pages/home/chat*") {
      return $true
    }
  }
  return $false
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
    X      = [int](($left + $right) / 2)
    Y      = [int](($top + $bottom) / 2)
    Bounds = $bounds
    Width  = $right - $left
    Height = $bottom - $top
  }
}

function Get-PromptNode {
  param([xml]$Xml)
  $node = Get-NodeByResourceId -Xml $Xml -ResourceId "prompt"
  if ($null -ne $node) { return $node }
  $nodes = $Xml.SelectNodes("//node[@class='android.widget.EditText' and @enabled='true']")
  foreach ($candidate in $nodes) {
    $bounds = [string]$candidate.bounds
    $m = [regex]::Match($bounds, "\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
    if ($m.Success -and [int]$m.Groups[2].Value -gt 1500) {
      return $candidate
    }
  }
  foreach ($candidate in $nodes) {
    $center = Get-BoundsCenter -Node $candidate
    if ($center.Y -gt 1600 -and $center.Width -gt 500) {
      return $candidate
    }
  }
  foreach ($candidate in $Xml.SelectNodes("//node[@clickable='true' and @enabled='true']")) {
    $center = Get-BoundsCenter -Node $candidate
    if ($center.Y -gt 1600 -and $center.Width -gt 500) {
      foreach ($edit in $nodes) {
        $editCenter = Get-BoundsCenter -Node $edit
        if ([math]::Abs($editCenter.Y - $center.Y) -lt 120) {
          return $edit
        }
      }
    }
  }
  if (Test-IsChatPage -Xml $Xml) {
    return [PSCustomObject]@{
      bounds = "[42,1700][1041,1866]"
      clickable = "true"
      enabled = "true"
      class = "virtual.prompt"
    }
  }
  return $null
}

function Get-ChatEntryNode {
  param([xml]$Xml)
  foreach ($candidate in $Xml.SelectNodes("//node[@clickable='true' and @enabled='true']")) {
    $center = Get-BoundsCenter -Node $candidate
    if ($center.Y -gt 1700 -and $center.Width -gt 500) {
      return $candidate
    }
  }
  return $null
}

function Get-SendNode {
  param([xml]$Xml)
  $node = Get-NodeByResourceId -Xml $Xml -ResourceId "send"
  if ($null -ne $node) { return $node }
  foreach ($candidate in $Xml.SelectNodes("//node[@clickable='true' and @enabled='true']")) {
    $center = Get-BoundsCenter -Node $candidate
    if ($center.Y -gt 1650 -and $center.X -gt 900 -and $center.Width -lt 180) {
      return $candidate
    }
  }
  return $null
}

function Ensure-ChatPage {
  param([xml]$Xml)
  $pageMarkers = Get-DumpPageMarkers -Xml $Xml
  if (Test-IsChatPage -Xml $Xml) {
    return $Xml
  }
  $chatEntryNode = Get-ChatEntryNode -Xml $Xml
  if ($null -eq $chatEntryNode) {
    throw "not on chat page and chat entry not found. pages=$($pageMarkers -join ',')"
  }
  $chatEntryCenter = Get-BoundsCenter -Node $chatEntryNode
  Step "Enter chat page"
  Invoke-Adb shell input tap $chatEntryCenter.X $chatEntryCenter.Y
  if ($LASTEXITCODE -ne 0) { throw "tap chat entry failed" }
  Start-Sleep -Seconds 2
  $chatPath = Dump-Ui -Name ("duomilu-enter-chat-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
  [xml]$chatXml = Get-Content -Raw -LiteralPath $chatPath -Encoding UTF8
  $chatPageMarkers = Get-DumpPageMarkers -Xml $chatXml
  if (-not (Test-IsChatPage -Xml $chatXml)) {
    throw "failed to enter chat page. pages=$($chatPageMarkers -join ',') dump=$chatPath"
  }
  return $chatXml
}

function Convert-ToAdbText {
  param([string]$Text)
  if ($Text -match "[^\x20-\x7E]") {
    if ([string]::IsNullOrWhiteSpace($AsciiFallbackPrompt)) {
      throw "adb shell input text only supports ASCII reliably. Provide -AsciiFallbackPrompt for non-ASCII prompts."
    }
    Write-Host "Prompt contains non-ASCII; using ASCII fallback prompt." -ForegroundColor Yellow
    $Text = $AsciiFallbackPrompt
  }
  $escaped = $Text.Replace(' ', '%s')
  $escaped = $escaped.Replace('&', '`&')
  $escaped = $escaped.Replace('|', '`|')
  $escaped = $escaped.Replace('<', '`<')
  $escaped = $escaped.Replace('>', '`>')
  $escaped = $escaped.Replace(';', '`;')
  return [PSCustomObject]@{
    Original = $Prompt
    Used     = $Text
    Escaped  = $escaped
  }
}

function Invoke-AdbInputText {
  param([string]$Text)
  try {
    Set-Clipboard -Value $Text
    Invoke-Adb shell input keyevent 279
    if ($LASTEXITCODE -eq 0) { return $Text }
  } catch {
    Write-Host "Clipboard paste unavailable; fallback to adb input text." -ForegroundColor Yellow
  }
  $converted = Convert-ToAdbText -Text $Text
  Invoke-Adb shell input text $converted.Escaped
  if ($LASTEXITCODE -ne 0) { throw "adb text input and paste both failed" }
  return $converted.Used
}

function Save-HostClipboard {
  try {
    $script:ClipboardSnapshot = Get-Clipboard -Raw
    $script:ClipboardCaptured = $true
  } catch {
    Write-Host "Clipboard snapshot unavailable; will not restore previous clipboard." -ForegroundColor Yellow
    $script:ClipboardSnapshot = $null
    $script:ClipboardCaptured = $false
  }
}

function Restore-HostClipboard {
  if (-not $script:ClipboardCaptured) {
    return
  }
  try {
    Set-Clipboard -Value $script:ClipboardSnapshot
  } catch {
    Write-Host "Failed to restore previous host clipboard." -ForegroundColor Yellow
  }
}

function Start-ClipboardRestoreGuard {
  if (-not $script:ClipboardCaptured) {
    return
  }
  New-Item -ItemType Directory -Force -Path $script:ClipboardGuardDir | Out-Null
  Set-Content -LiteralPath $script:ClipboardGuardSnapshotPath -Value $script:ClipboardSnapshot -Encoding UTF8
  if (Test-Path -LiteralPath $script:ClipboardGuardCancelPath) {
    Remove-Item -LiteralPath $script:ClipboardGuardCancelPath -Force -ErrorAction SilentlyContinue
  }
  $guardScript = @'
param(
  [string]$SnapshotPath,
  [string]$CancelPath
)
Start-Sleep -Seconds 20
if (Test-Path -LiteralPath $CancelPath) {
  return
}
if (-not (Test-Path -LiteralPath $SnapshotPath)) {
  return
}
try {
  $snapshot = Get-Content -LiteralPath $SnapshotPath -Raw -Encoding UTF8
  Set-Clipboard -Value $snapshot
} catch {
}
'@
  $script:ClipboardGuardProc = Start-Process -FilePath "powershell.exe" `
    -ArgumentList @(
      "-NoProfile",
      "-ExecutionPolicy", "Bypass",
      "-WindowStyle", "Hidden",
      "-Command", $guardScript,
      "-SnapshotPath", $script:ClipboardGuardSnapshotPath,
      "-CancelPath", $script:ClipboardGuardCancelPath
    ) `
    -WindowStyle Hidden `
    -PassThru
}

function Stop-ClipboardRestoreGuard {
  if (-not $script:ClipboardCaptured) {
    return
  }
  try {
    New-Item -ItemType File -Path $script:ClipboardGuardCancelPath -Force | Out-Null
  } catch {
  }
  foreach ($path in @($script:ClipboardGuardSnapshotPath, $script:ClipboardGuardCancelPath)) {
    if (Test-Path -LiteralPath $path) {
      Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
  }
}

function Clear-PromptInput {
  param($PromptNode)
  if ($null -eq $PromptNode) {
    throw "prompt node is null"
  }
  $promptCenter = Get-BoundsCenter -Node $PromptNode
  Step "Clear prompt input"
  Invoke-Adb shell input tap $promptCenter.X $promptCenter.Y
  if ($LASTEXITCODE -ne 0) { throw "tap prompt for clear failed" }
  Start-Sleep -Milliseconds 400
  for ($attempt = 0; $attempt -lt 60; $attempt++) {
    Invoke-Adb shell input keyevent 67 | Out-Null
  }
  Start-Sleep -Milliseconds 400
}

try {
  Save-HostClipboard
  Start-ClipboardRestoreGuard

  Ensure-AdbOk
  $focusText = Assert-AppInForeground -Pkg $PackageName
  Step "Dump UI before input"
  $beforePath = Dump-Ui -Name ("duomilu-before-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
  [xml]$beforeXml = Get-Content -Raw -LiteralPath $beforePath -Encoding UTF8
  $beforeXml = Ensure-ChatPage -Xml $beforeXml

  $promptNode = Get-PromptNode -Xml $beforeXml
  if ($null -eq $promptNode) {
    $chatEntryNode = Get-ChatEntryNode -Xml $beforeXml
    if ($null -ne $chatEntryNode) {
      $chatEntryCenter = Get-BoundsCenter -Node $chatEntryNode
      Step "Re-enter chat to activate composer"
      Invoke-Adb shell input tap $chatEntryCenter.X $chatEntryCenter.Y
      if ($LASTEXITCODE -ne 0) { throw "tap chat entry for composer activation failed" }
      Start-Sleep -Seconds 2
      $beforePath = Dump-Ui -Name ("duomilu-before-reactivated-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
      [xml]$beforeXml = Get-Content -Raw -LiteralPath $beforePath -Encoding UTF8
      $promptNode = Get-PromptNode -Xml $beforeXml
    }
  }

  if ($null -eq $promptNode) {
    throw "prompt input not found in UI dump: $beforePath"
  }
  $promptCenter = Get-BoundsCenter -Node $promptNode

  Clear-PromptInput -PromptNode $promptNode

  Step "Input prompt"
  $usedPrompt = Invoke-AdbInputText -Text $Prompt
  Start-Sleep -Milliseconds 800

  if ($PressEnterInsteadOfTapSend) {
    Step "Send by Enter"
    Invoke-Adb shell input keyevent 66
    if ($LASTEXITCODE -ne 0) { throw "send keyevent failed" }
  } else {
    Step "Tap send button"
    $midPath = Dump-Ui -Name ("duomilu-before-send-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    [xml]$midXml = Get-Content -Raw -LiteralPath $midPath -Encoding UTF8
    $sendNode = Get-SendNode -Xml $midXml
    if ($null -eq $sendNode) {
      Step "Send button missing, fallback to Enter"
      Invoke-Adb shell input keyevent 66
      if ($LASTEXITCODE -ne 0) { throw "send keyevent fallback failed" }
    } else {
      $sendCenter = Get-BoundsCenter -Node $sendNode
      if ([string]$sendNode.enabled -eq "false") {
        throw "send button is disabled. bounds=$($sendCenter.Bounds)"
      }
      Invoke-Adb shell input tap $sendCenter.X $sendCenter.Y
      if ($LASTEXITCODE -ne 0) { throw "tap send failed" }
    }
  }

  Start-Sleep -Seconds $AfterSendWaitSeconds
  Step "Dump UI after send"
  $afterPath = Dump-Ui -Name ("duomilu-after-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
  [xml]$afterXml = Get-Content -Raw -LiteralPath $afterPath -Encoding UTF8
  $statusNode = Get-NodeByResourceId -Xml $afterXml -ResourceId "status"
  $sendAfterNode = Get-SendNode -Xml $afterXml

  $result = [PSCustomObject]@{
    status             = "sent"
    device_id          = $DeviceId
    package_name       = $PackageName
    focus              = $focusText
    prompt             = $Prompt
    used_prompt        = $usedPrompt
    prompt_bounds      = $promptCenter.Bounds
    before_dump        = $beforePath
    after_dump         = $afterPath
    host_clipboard_mode = $(if ($script:ClipboardCaptured) { "guarded_restore" } else { "not_captured" })
    status_text        = $(if ($statusNode) { [string]$statusNode.text } else { "" })
    send_text          = $(if ($sendAfterNode) { [string]$sendAfterNode.text } else { "" })
    send_enabled       = $(if ($sendAfterNode) { [string]$sendAfterNode.enabled } else { "" })
  }
  $result | ConvertTo-Json -Depth 4
} finally {
  Restore-HostClipboard
  Stop-ClipboardRestoreGuard
}
