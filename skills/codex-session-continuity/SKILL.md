---
name: codex-session-continuity
description: "Checkpoint and resume Codex project work across context compaction, MCP refreshes, restarts, or handoff to a fresh session."
---

# Codex Session Continuity

## Core Rule

Treat Codex as a replaceable stage executor. Keep durable task state in the project, not only in the chat.

Use project-local memory:

```text
.codex-memory/
  index.md
  current-task.json
  tasks/
  threads/
```

Do not rely on `codex resume --last` when multiple Codex sessions may be running. Prefer project state cards plus a fresh Codex session.

## When The User Wants A Restart

Before ending or restarting, write a checkpoint:

1. Current objective.
2. Current stage.
3. Completed actions.
4. Current blocker or reason for restart.
5. Evidence paths.
6. Next action.
7. Stop conditions.
8. MCP/App/backend state if relevant.

Use the bundled script when possible:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\codex-session-continuity\scripts\codex_checkpoint.ps1" `
  -ProjectRoot "D:\hanhan\app" `
  -Objective "..." `
  -Stage "..." `
  -NextAction "..."
```

Then tell the user how to start a fresh session, or run the resume script if asked.

For the one-command restart flow, use the one-shot worker:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\codex-session-continuity\scripts\codex_restart_once.ps1" `
  -ProjectRoot "D:\hanhan\app" `
  -Objective "..." `
  -Stage "..." `
  -NextAction "..."
```

This writes the checkpoint and starts a new PowerShell process that launches a fresh Codex session with the restore prompt. It does not close the current Codex. Tell the user to close the old session after the new one is restored.

## Fresh Session Restore

In a fresh Codex, restore from files, not from a long chat:

1. Read `.codex-memory/index.md`.
2. Read `.codex-memory/current-task.json`.
3. Read only the relevant thread file under `.codex-memory/threads/`.
4. Continue from `next_action`.

Use the bundled script to start a new Codex process with a restore prompt:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.codex\skills\codex-session-continuity\scripts\codex_resume_project.ps1" `
  -ProjectRoot "D:\hanhan\app"
```

## MCP Refresh Guidance

Separate three cases:

```text
App repackaged only
  -> Codex restart is usually unnecessary.

Backend/runtime implementation changed behind the same MCP tool schema
  -> Prefer restarting backend/runtime only.

MCP tool names or schemas changed, or stdio transport is closed
  -> Start a fresh Codex session after checkpointing.
```

Prefer stable MCP tools such as `mobile_execute_action(action,payload)` and `mobile_tool_manifest()` so new runtime actions do not force a Codex restart.

## Compact Guidance

Use `compact` for ordinary context pressure. Use checkpoint + fresh session when:

- Images, long logs, or screenshots have polluted context.
- Multiple Codex sessions make `resume --last` ambiguous.
- MCP tool schema must reload.
- The next stage should start with a concise state card.

## Safety

- Do not run `git add`, `git reset`, or staged-area operations unless the user explicitly asks.
- Do not kill Codex from inside the current Codex process and assume it can continue.
- If launching a new Codex, keep the old session alive unless the user explicitly wants it closed.
- Prefer `codex_restart_once.ps1` over a long-running daemon unless the user explicitly asks for a watcher.
- For project memory, write only inside the current project `.codex-memory/`.
