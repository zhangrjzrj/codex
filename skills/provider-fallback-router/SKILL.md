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

## Workflow

1. Create or update the local router implementation.
2. Bind the client to the local router instead of binding it directly to an upstream provider.
3. Put the primary and backup upstream values in environment variables or local config.
4. Verify the router with one success case and one forced-failure fallback case.
5. If the client already has a provider setting, point it at the router and keep the upstreams hidden behind the router.

## Constraints

- Do not store real API keys in the skill.
- Do not add health scoring, database state, queueing, or multi-hop fallback unless the user explicitly asks.
- Do not replace the user's chosen client or API family; only insert the routing layer in front of it.

## Expected result

The client talks to one local base URL, and the router decides whether the request goes to the primary upstream or the backup upstream.
