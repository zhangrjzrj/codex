---
name: "hanhan-app1234-sync"
description: "Submit and synchronize Hanhan frontend app1/app2/app3/app4 workspaces. Use when the user says phrases like '先提交app1234前端代码，然后fetch远端最新，然后rebase，推送，然后再更新app1234到最新', asks to sync all app1234 frontend spaces, or wants app1-4 checked for unpushed commits, rebased, pushed, and refreshed to the latest remote branch."
---

# Hanhan App1234 Sync

## Purpose

Run the standard app1-4 frontend sync loop:

1. Inspect `D:\hanhan\app1` through `D:\hanhan\app4`.
2. Commit only intended frontend changes in any dirty space.
3. Fetch `origin app_private`.
4. Rebase spaces with local commits onto `origin/app_private`.
5. Push rebased local commits.
6. Fetch again and rebase all app1-4 spaces to the latest `origin/app_private`.
7. Report final `git status --short --branch` for all four spaces.

## Required Coordination

Use `hanhan-app-space-sync` when promotion through the shared `D:\hanhan\app` repo is needed, or when unclassified files/local config preservation may matter.

For the direct app1234 flow, stay conservative:

- Do not run destructive Git commands.
- Do not touch staged changes unless the user explicitly asked.
- Do not force-push.
- Stop on conflicts, dirty unrelated files, or unclear untracked files.
- Keep commit messages in Chinese.
- Preserve space-local config and helper files unless the user explicitly wants them shared.

## Minimal Command Pattern

Use this pattern after inspecting each workspace:

```powershell
foreach($s in 'app1','app2','app3','app4'){
  git -C "D:\hanhan\$s" status --short --branch
}
```

For spaces with intended committed changes:

```powershell
git -C "D:\hanhan\<space>" fetch origin app_private
git -C "D:\hanhan\<space>" rebase origin/app_private
git -C "D:\hanhan\<space>" push origin app_private
```

Then refresh all spaces:

```powershell
foreach($s in 'app1','app2','app3','app4'){
  git -C "D:\hanhan\$s" fetch origin app_private
  git -C "D:\hanhan\$s" rebase origin/app_private
  git -C "D:\hanhan\$s" status --short --branch
}
```

## Final Report

Report:

- which spaces had commits
- which commits were pushed
- whether all app1-4 spaces match `origin/app_private`
- any skipped or blocked files
