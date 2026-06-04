---
name: "codex-reboot-restore"
description: "Save active Codex CLI sessions before a Windows reboot and reopen them afterward. Use when the user wants to record all currently open Codex CLI instances, restore multiple Codex sessions after restarting the computer, inspect a saved Codex reboot snapshot, or generate commands to resume many Codex sessions from one Codex."
---

# Codex Reboot Restore

## Purpose

Capture a reboot snapshot of active Codex CLI sessions and later reopen them in separate Windows terminal windows or tabs.

This skill cannot resurrect a dead process in-place. It restores by launching new `codex resume <session-id>` processes from saved session metadata.

## Workflow

Use `scripts/codex_reboot_restore.ps1`.

Before reboot:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:CODEX_HOME\skills\codex-reboot-restore\scripts\codex_reboot_restore.ps1" -Action save
```

After reboot, from one Codex:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:CODEX_HOME\skills\codex-reboot-restore\scripts\codex_reboot_restore.ps1" -Action restore
```

Restore uses full Codex permissions by default:

```text
--dangerously-bypass-approvals-and-sandbox
```

To restore without full permissions:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:CODEX_HOME\skills\codex-reboot-restore\scripts\codex_reboot_restore.ps1" -Action restore -NoFullAccess
```

To inspect without opening terminals:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:CODEX_HOME\skills\codex-reboot-restore\scripts\codex_reboot_restore.ps1" -Action list
```

## Behavior

- Prefer exact session ids found in running Codex command lines, especially `codex resume <session-id>`.
- Also scan recent `CODEX_HOME\sessions\**\rollout-*.jsonl` files and record candidates that were recently modified.
- Read each session file's first `session_meta` line to extract `id` and `cwd`.
- Restore exact sessions by default.
- Restore candidate sessions only when the script is run with `-IncludeCandidates`.
- Restore sessions with `--dangerously-bypass-approvals-and-sandbox` by default; pass `-NoFullAccess` to disable this.
- Launch with Windows Terminal (`wt`) when available; otherwise fall back to `Start-Process powershell`.

## Safety

- Do not delete, archive, or mutate Codex sessions.
- Do not run `git` or project commands during save/list/restore.
- Treat plain running `codex` processes without an explicit session id as candidates, because Windows process command lines do not expose the internal session id.
- If a snapshot contains uncertain candidates, tell the user they can restore them with `-IncludeCandidates`.
- Default restore opens full-access Codex sessions. Use `-NoFullAccess` when the user wants normal permissions.

## Snapshot Location

Default:

```text
$CODEX_HOME\reboot-restore\latest.json
```

When `CODEX_HOME` is unset, use:

```text
$HOME\.codex\reboot-restore\latest.json
```
