---
name: "codex-reboot-restore"
description: "Save active Codex CLI sessions before a Windows reboot and reopen them afterward. Use when the user wants to record all currently open Codex CLI instances, restore multiple Codex sessions after restarting the computer, inspect a saved Codex reboot snapshot, or generate commands to resume many Codex sessions from one Codex."
---

# Codex Reboot Restore

## Purpose

Capture a reboot snapshot of active Codex CLI sessions and later reopen them in separate Windows terminal windows or tabs.

This skill cannot resurrect a dead process in-place. It restores by launching new `codex resume <session-id>` processes from saved session metadata.

The snapshot also stores a best-effort window title for each session. It resolves titles in this order:

1. `$CODEX_HOME\reboot-restore\window-titles.json` session-id mapping
2. recent session text such as `/rename ...` or `当前窗口主题：...`
3. directly exposed process window title, when available

Windows Terminal does not reliably expose every tab's custom title to child processes, so the mapping or explicit session text is the stable fallback.

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

Restore also enables TUI color highlighting by default in each new process. It clears inherited `NO_COLOR`, sets `TERM=xterm-256color`, and sets `COLORTERM=truecolor` before running `codex resume`. This prevents a controlling sandbox or non-interactive shell from accidentally forcing the restored TUI into monochrome mode. These changes apply only to the restored process, not to user or machine environment variables.

To preserve the inherited color environment instead:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:CODEX_HOME\skills\codex-reboot-restore\scripts\codex_reboot_restore.ps1" -Action restore -NoColorRestore
```

To restore without full permissions:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:CODEX_HOME\skills\codex-reboot-restore\scripts\codex_reboot_restore.ps1" -Action restore -NoFullAccess
```

To resume a session with a different provider or model while preserving its context:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:CODEX_HOME\skills\codex-reboot-restore\scripts\codex_reboot_restore.ps1" -Action restore -ModelProvider duckcoding -Model gpt-5.6-sol
```

`resume` can retain the provider recorded in the session. Use `-ModelProvider` to pass an explicit `-c model_provider=...` override and `-Model` to pass an explicit model override. If the new window reports a read-only `.codex` database or access denied under `CodexSandboxUsers`, run the restore command from outside the sandbox with elevated execution approval; do not delete or rewrite the session database.

To inspect without opening terminals:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:CODEX_HOME\skills\codex-reboot-restore\scripts\codex_reboot_restore.ps1" -Action list
```

To preview restore commands without opening terminals:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:CODEX_HOME\skills\codex-reboot-restore\scripts\codex_reboot_restore.ps1" -Action restore -DryRun
```

## Behavior

- Prefer exact session ids found in running Codex command lines, especially `codex resume <session-id>`.
- Also scan recent `CODEX_HOME\sessions\**\rollout-*.jsonl` files and record candidates that were recently modified.
- Read each session file's first `session_meta` line to extract `id` and `cwd`.
- Save `title` and `title_source` when a title can be resolved.
- Restore exact sessions by default.
- Restore candidate sessions only when the script is run with `-IncludeCandidates`.
- Restore sessions with `--dangerously-bypass-approvals-and-sandbox` by default; pass `-NoFullAccess` to disable this.
- Preserve session context while allowing explicit provider/model overrides through `-ModelProvider` and `-Model`.
- Restore TUI color highlighting by default through process-local color environment values; pass `-NoColorRestore` to preserve the inherited environment.
- Launch with Windows Terminal (`wt`) when available and pass `new-tab --title`; otherwise fall back to `Start-Process powershell` and set `$host.UI.RawUI.WindowTitle`.

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

Optional title mapping:

```text
$CODEX_HOME\reboot-restore\window-titles.json
```

Example:

```json
{
  "019e9686-378d-7900-9097-c4b19bc9f4ff": "nbg"
}
```
