---
name: "provider-fallback-router"
description: "Create or update a local OpenAI-compatible fallback router for Codex or similar clients when you need one stable entrypoint that can fail over between two upstream providers."
---

# Provider Fallback Router

Use this skill when the user wants a reusable local routing layer that sends requests to one primary upstream and falls back to one backup upstream.

## Scope

- Keep the router minimal.
- Expose one local OpenAI-compatible base URL.
- Use a fixed provider order unless the user asks for a different one.
- Prefer config and environment variables over hardcoded secrets.

## Local Auth Prerequisite

The logon startup script requires a local, untracked credentials file:

```text
%USERPROFILE%\.codex\auth.json.bf
```

It must contain valid values for these fields:

```json
{
  "OPENAI_API_KEY_codexzh_888": "<local secret>",
  "OPENAI_API_KEY_duckcoding": "<local secret>"
}
```

The file is read only on the local machine. It is intentionally excluded from Git and must not be committed, copied into the skill, or printed in logs. If the file is missing or either field is empty, `scripts/start_router_at_logon.ps1` cannot start the router. Preparing this file is a deployment prerequisite when installing the skill on another machine.

## Workflow

1. Use `scripts/fallback_router.py` as the local router implementation.
2. Bind the client to `http://127.0.0.1:8787/v1` instead of binding it directly to an upstream provider.
3. Put the primary and backup upstream values in `J_PRIMARY_BASE`, `J_PRIMARY_KEY`, `J_SECONDARY_BASE`, and `J_SECONDARY_KEY`.
4. Start the router with `scripts/run_fallback_router.ps1`; it must launch a detached background process so closing the CLI does not stop the router.
5. The launcher must remove inherited `HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY` values when they point to an unavailable local proxy; upstream connectivity must be tested directly.
6. Verify `http://127.0.0.1:8787/health`, then run `scripts/fallback_router_smoke.py`, including one forced-failure fallback case.
7. If the client already has a provider setting, point it at the router and keep the upstreams hidden behind the router.

## Persistence on Windows

Use the detached launcher for a one-off session. When the router should survive computer restarts, configure a Windows Task Scheduler task that runs at the current user's logon:

```powershell
$python = (Get-Command python.exe).Source
$script = "$env:USERPROFILE\.codex\skills\provider-fallback-router\scripts\start_router_at_logon.ps1"
$action = New-ScheduledTaskAction -Execute "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $script + '"')
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName "JFallbackRouter" -Action $action -Trigger $trigger -Principal $principal -Force
```

After installation, verify both the task and the router:

```powershell
Get-ScheduledTask -TaskName "JFallbackRouter"
curl.exe http://127.0.0.1:8787/health
```

Remove the optional startup task with `Unregister-ScheduledTask -TaskName "JFallbackRouter" -Confirm:$false`.

## Constraints

- Do not store real API keys in the skill.
- Do not add health scoring, database state, queueing, or multi-hop fallback unless the user explicitly asks.
- Do not replace the user's chosen client or API family; only insert the routing layer in front of it.

## Expected result

The client talks to one local base URL, and the router decides whether the request goes to the primary upstream or the backup upstream.

## Scripts

- `scripts/fallback_router.py`: local OpenAI-compatible HTTP router.
- `scripts/run_fallback_router.ps1`: validates required environment variables and starts the router.
- `scripts/fallback_router_smoke.py`: runs an isolated primary-failure-to-backup test.
- `scripts/start_router_at_logon.ps1`: reads local auth settings and starts the router through the skill launcher at user logon.
