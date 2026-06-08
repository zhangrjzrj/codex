---
name: "windows-dialog-watchdog"
description: "Start and use a Windows dialog watchdog for Codex feedback loops, long-running tests, game/client automation, or debugging sessions that may hang behind modal dialogs. Use when Codex needs to detect standard Windows error popups, map dialogs to process IDs, save evidence, auto-close repeated dialogs, or kill target processes after a modal dialog storm."
---

# Windows Dialog Watchdog

Use this skill before or during Windows feedback loops that could be blocked by modal dialogs. The bundled script scans top-level Windows windows, maps each window to its owning PID, reads visible child text when possible, writes JSONL evidence, and can optionally close dialogs or kill repeated offending processes.

## Quick Start

Prefer dry-run first:

```powershell
python C:\Users\zhangruojun\.codex\skills\windows-dialog-watchdog\scripts\dialog_watchdog.py --watch --interval 1 --process-name Messiah --keyword "Cannot find resource dependence"
```

Use an explicit evidence directory when working in a project:

```powershell
python C:\Users\zhangruojun\.codex\skills\windows-dialog-watchdog\scripts\dialog_watchdog.py --watch --evidence-dir .codex-memory\tasks\dialog-watchdog --process-name Messiah --keyword "Cannot find resource dependence"
```

Enable actions only after dry-run proves PID and dialog text are correct:

```powershell
python C:\Users\zhangruojun\.codex\skills\windows-dialog-watchdog\scripts\dialog_watchdog.py --watch --auto-close --auto-kill --kill-threshold 3 --process-name Messiah --keyword "Cannot find resource dependence"
```

## Workflow

1. Start watchdog before launching or attaching to the target app.
2. Prefer `--pid <pid>` if the launcher/test harness knows the exact PID.
3. If PID is unknown, filter with `--process-name`, `--process-path-contains`, and `--keyword`.
4. Keep the first run in dry-run mode. Inspect `events.jsonl` and confirm the reported PID, process path, dialog title, and dialog text.
5. Turn on `--auto-close` to close matched dialogs.
6. Turn on `--auto-kill` only for clearly matched target processes and repeated dialog storms.
7. When a feedback loop disconnects or the target process exits, read the latest watchdog evidence before diagnosing code.

## Evidence

The script writes one JSON object per matched dialog to:

```text
<evidence-dir>\events.jsonl
```

Each event includes timestamp, HWND, title, child text, matched keywords, PID, process name, process path, repeat count, action, and reason. If `--screenshot` is enabled, it also tries to save a desktop screenshot beside the event log.

Repeat counting defaults to signature mode: same PID plus same matched keyword set is treated as the same dialog storm. This handles resource-dependency popups where each dialog has a different asset path but the same error signature. Use `--repeat-key-mode exact` only when the full dialog text should be treated as part of identity.

Default evidence directory:

```text
<current-project>\.codex-memory\tasks\dialog-watchdog
```

If the current directory has no `.codex-memory`, pass `--evidence-dir` explicitly.

## Safety Rules

- Dry-run is the default and must be used first for a new target.
- Do not use broad `--auto-kill` without a PID, process path filter, or narrow process-name plus keyword filter.
- For multiple target instances, prefer `--pid`.
- Run the watchdog elevated when the target app is elevated; otherwise Windows may block reading or closing some windows.
- Treat game-engine self-drawn panels as out of scope unless they appear as real Windows windows.

## Script

Bundled script:

```text
scripts/dialog_watchdog.py
```

Common options:

```text
--watch                     Keep scanning until stopped.
--once                      Scan once and exit.
--interval 1                Watch interval in seconds.
--pid 1234                  Match exact process PID; repeatable.
--process-name Messiah      Match process name substring; repeatable.
--process-path-contains F:\ Match process path substring; repeatable.
--keyword "Cannot find"     Match title/text substring; repeatable.
--auto-close                Send WM_CLOSE to matched dialog windows.
--auto-kill                 Kill owning process after threshold.
--kill-threshold 3          Repeated matched dialogs before kill.
--repeat-key-mode signature Group repeats by PID and matched keywords.
--max-events 20             Stop after this many matched events.
--screenshot                Try to save desktop screenshot per event.
```
