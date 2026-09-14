---
name: "provider-fallback-router"
description: "Create or update a minimal local OpenAI-compatible two-provider fallback router for Codex or similar clients."
---

# Provider Fallback Router

Use the behavior defined by `F:\ue\ds\provider-fallback-routing-spec.md`.

## Runtime

- Codex connects to `http://127.0.0.1:8787/v1`.
- `J_PRIMARY_*` and `J_SECONDARY_*` are the only provider-order source.
- `scripts/start_router_at_logon.ps1` reads `OPENAI_API_KEY_codexzh_888` and `OPENAI_API_KEY_qcode` from `%USERPROFILE%\.codex\auth.json`.
- `scripts/run_fallback_router.ps1` starts the detached router through `scripts/start_fallback_router.py`.

## Rules

- Try the primary once.
- Before any response is delivered to Codex, fall back once on connection failure, timeout, HTTP 401/403/429/5xx, or failure to read the expected first response body chunk.
- After response delivery starts, never join a second provider response.
- Treat `127.0.0.1:8787` as the router's exclusive port and replace its current listener whenever the logon launcher runs.
- Do not store keys, provider health, request history, or routing state.

## Validation

Run `scripts/fallback_router_smoke.py` on isolated random ports. After changing this skill, run `quick_validate.py`, Python parsing checks, and PowerShell parsing checks.
