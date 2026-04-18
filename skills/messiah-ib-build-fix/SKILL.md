---
name: messiah-ib-build-fix
description: Compile the Messiah Windows solution with IncrediBuild (BuildConsole), persist machine-readable build logs, extract actionable MSVC/LNK/MSBuild errors, and run an iterative fix-and-rebuild loop. Use when a user asks to compile/build Messiah, wants Batch Build/IncrediBuild behavior, needs build error triage, or asks for automatic compile-fix retries.
---

# Messiah IB Build Fix

## Overview

Use this skill to run reproducible Messiah Windows builds through IncrediBuild from the CLI and keep logs that Codex can parse, patch, and retry against.

## Workflow

1. Confirm build target.
- Default target is `Messiah.Windows.sln` with `Hybrid|x64`.
- If the user gives a different target (`Release`, project-only build, `rebuild`, `clean`), honor it.

2. Run build through script (prefer project script; fallback to global skill script).
- **Project workspace**: the code repo you are building (e.g. `F:\messiah_h74_new_branch`).
- **Codex global config repo**: `C:\Users\zhangruojun\.codex` (contains global `skills/` + `AGENTS.md`).
- Prefer the project workspace script `scripts/invoke_ib_build.ps1` when it exists.
- If the project workspace does not have it, use the global skill script under `...\.codex\skills\messiah-ib-build-fix\scripts\invoke_ib_build.ps1`.
- Always persist logs under `.codex-build/logs/` and capture metadata JSON.
- If the user wants faster triage, enable `-FailFastOnFirstError` to stop as soon as the first compiler/linker error is detected in the output log.

3. Parse errors.
- Use `scripts/parse_ib_log.py` against the newest `*.out.log`.
- Prioritize error codes and files with highest frequency first.

4. Apply safe fixes.
- Patch only the smallest set of files needed for current top errors.
- Avoid speculative refactors, broad formatting changes, and unrelated cleanup.
- If the same error signature appears unchanged in two rounds, stop and report blocker.

5. Retry loop.
- Repeat build -> parse -> patch up to five rounds.
- Stop early on success (build exit code 0 and zero parsed errors).

## Commands

Run default Hybrid build (prefer project script, fallback to global skill script):
```powershell
$projectScript = "scripts/invoke_ib_build.ps1"
$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$globalScript = Join-Path $codexRoot "skills/messiah-ib-build-fix/scripts/invoke_ib_build.ps1"

$scriptToRun = if (Test-Path -LiteralPath $projectScript) { $projectScript } else { $globalScript }
powershell -ExecutionPolicy Bypass -File $scriptToRun
```

Run rebuild for Release:
```powershell
$projectScript = "scripts/invoke_ib_build.ps1"
$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$globalScript = Join-Path $codexRoot "skills/messiah-ib-build-fix/scripts/invoke_ib_build.ps1"
$scriptToRun = if (Test-Path -LiteralPath $projectScript) { $projectScript } else { $globalScript }
powershell -ExecutionPolicy Bypass -File $scriptToRun -Action rebuild -Configuration Release
```

Run fail-fast triage build:
```powershell
$projectScript = "scripts/invoke_ib_build.ps1"
$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$globalScript = Join-Path $codexRoot "skills/messiah-ib-build-fix/scripts/invoke_ib_build.ps1"
$scriptToRun = if (Test-Path -LiteralPath $projectScript) { $projectScript } else { $globalScript }
powershell -ExecutionPolicy Bypass -File $scriptToRun -FailFastOnFirstError
```

Parse the latest output log:
```powershell
python scripts/parse_ib_log.py --latest-from .codex-build/logs
```

## Guardrails

- Never run destructive git commands unless explicitly requested.
- Keep each patch tightly scoped to current compiler errors.
- Preserve existing user changes in dirty worktrees.
- Report what changed each round: touched files, resolved errors, and blockers.

## Resources

- `scripts/invoke_ib_build.ps1` (project workspace): Runs IncrediBuild (`BuildConsole`) and writes logs plus metadata.
- `C:\Users\zhangruojun\.codex\skills\messiah-ib-build-fix\scripts\invoke_ib_build.ps1` (Codex global config repo): Fallback build runner when the project workspace does not include the script.
- `scripts/parse_ib_log.py`: Extracts structured errors/warnings and prints a ranked summary.
- `references/error-playbook.md`: Fix heuristics for common MSVC/LNK/MSBuild errors.

