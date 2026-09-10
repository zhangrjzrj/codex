$ErrorActionPreference = "Stop"

$authPath = Join-Path $env:USERPROFILE ".codex\auth.json.bf"
$auth = Get-Content -Raw $authPath | ConvertFrom-Json

$env:J_PRIMARY_BASE = "https://api.codexzh.com/v1"
$env:J_PRIMARY_KEY = $auth.OPENAI_API_KEY_codexzh_888
$env:J_SECONDARY_BASE = "https://api.duckcoding.ai/v1"
$env:J_SECONDARY_KEY = $auth.OPENAI_API_KEY_duckcoding
$env:J_HOST = "127.0.0.1"
$env:J_PORT = "8787"
$env:J_TIMEOUT_SEC = "60"

foreach ($name in @("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")) {
    Remove-Item "Env:$name" -ErrorAction SilentlyContinue
}

$listener = Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    exit 0
}

& (Join-Path $PSScriptRoot "run_fallback_router.ps1")
