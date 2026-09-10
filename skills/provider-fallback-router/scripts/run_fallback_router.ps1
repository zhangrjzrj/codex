$ErrorActionPreference = "Stop"

if (-not $env:J_PRIMARY_BASE -or -not $env:J_PRIMARY_KEY -or -not $env:J_SECONDARY_BASE -or -not $env:J_SECONDARY_KEY) {
    throw "Set J_PRIMARY_BASE, J_PRIMARY_KEY, J_SECONDARY_BASE, and J_SECONDARY_KEY first."
}

$env:J_HOST = if ($env:J_HOST) { $env:J_HOST } else { "127.0.0.1" }
$env:J_PORT = if ($env:J_PORT) { $env:J_PORT } else { "8787" }

python "$PSScriptRoot\start_fallback_router.py"
