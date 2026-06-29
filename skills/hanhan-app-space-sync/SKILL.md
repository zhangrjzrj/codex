---
name: "hanhan-app-space-sync"
description: "Sync shared frontend changes across D:\\hanhan\\app and D:\\hanhan\\app1-4. Use when Codex needs to: (1) check whether app1/app2/app3/app4 contain commits not yet merged into hanhan/app, (2) audit newly added or unclassified files before bulk sync, (3) promote committed shared fixes from a space repo back into hanhan/app, (4) push hanhan/app to its remote, and (5) refresh one or more app spaces to the latest shared branch while preserving each space's local environment/config files."
---

# Hanhan App Space Sync

## Overview

Standardize the multi-workspace sync flow around `D:\hanhan\app` as the shared source of truth.

Use this skill when the goal is:

- collect committed shared fixes from `app1/2/3/4` into `app`
- avoid merging space-only local config into `app`
- push the shared branch after promotion
- rebase a target space onto the latest shared branch without losing local config files

This skill is intentionally conservative. It will stop instead of overwriting dirty non-config files.

## Workflow

1. Commit any shared fix in the source space first.
   Dirty shared code is not promoted by the script.
2. Run `inventory` to see divergence between `app` and `app1-4`, and inspect any `unclassified_paths`.
3. Classify any newly added paths before bulk sync:
   - add space-local files to the preserve list
   - keep shared files in normal shared directories so they can be promoted
4. Run `promote-main` to cherry-pick committed shared fixes from the spaces into `app`.
5. Push `app` to the shared remote.
6. Run `refresh-space` for the target workspace to rebase onto the latest shared branch while preserving local config.

## Commands

The bundled script is:

```powershell
scripts/sync_hanhan_app.ps1
```

Typical usage:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync_hanhan_app.ps1 -Mode inventory
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync_hanhan_app.ps1 -Mode promote-main -Push
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync_hanhan_app.ps1 -Mode refresh-space -Space app3
```

## Default Preserve Rules

Default preserved local-config paths are documented in [references/preserve-paths.md](references/preserve-paths.md).

These are treated as space-local:

- `config/localDebug.js`
- local pack/install helper scripts under `scripts/`

Do not promote these into `hanhan/app` unless the user explicitly wants to change the shared baseline.

## Unclassified File Gate

The script now treats newly added files outside the preserve list and shared path prefixes as `unclassified`.

- `inventory` reports these paths per space in `unclassified_paths`
- `promote-main` stops if any source space still has unclassified paths
- `refresh-space` stops if the target space still has unclassified paths

This is intentional. It prevents silent loss of new local-only files and silent omission of new shared files.

## Safety Rules

- Read the inventory first before promoting.
- Treat `hanhan/app` as the shared branch owner.
- Promote only committed changes from the spaces into `app`.
- Resolve `unclassified_paths` before promote or refresh.
- If a workspace has dirty non-preserved files, stop and report the blocker.
- Keep commit titles unchanged when the commit is promoted as-is.
- If a commit only changes preserved local-config files, skip it during main promotion.

## Current Limitation

- `promote-main` only reads commits, not dirty shared worktree edits.
- If a space has an uncommitted shared fix, commit it first, then rerun the skill.
- `refresh-space` rebases the live workspace and will only proceed when dirty files are limited to preserved paths.
- Shared path recognition still uses path prefixes. If the repo adds a new shared top-level directory, extend the script before bulk sync.
