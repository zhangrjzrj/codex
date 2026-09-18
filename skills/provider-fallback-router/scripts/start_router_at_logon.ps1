$ErrorActionPreference = "Stop"

$auth = Get-Content -Raw (Join-Path $env:USERPROFILE ".codex\auth.json") | ConvertFrom-Json

$env:J_PRIMARY_BASE = "https://asia.qcode.cc/openai"
$env:J_PRIMARY_KEY = $auth.OPENAI_API_KEY_qcode
$env:J_SECONDARY_BASE = "https://api.codexzh.com/v1"
$env:J_SECONDARY_KEY = $auth.OPENAI_API_KEY_codexzh_888
$env:J_HOST = "127.0.0.1"
$env:J_PORT = "8787"
$env:J_TIMEOUT_SEC = "60"

$listener = netstat.exe -ano -p TCP | Select-String "^\s*TCP\s+127\.0\.0\.1:$($env:J_PORT)\s+\S+\s+LISTENING\s+(\d+)\s*$" | Select-Object -First 1
if ($listener) {
    $ownerPid = [int]$listener.Matches[0].Groups[1].Value
    $owner = Get-Process -Id $ownerPid
    $owner.Kill()
    if (-not $owner.WaitForExit(5000)) {
        throw "Process $ownerPid did not exit after replacement was requested."
    }
}

& (Join-Path $PSScriptRoot "run_fallback_router.ps1")
