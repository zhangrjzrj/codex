---
name: "update-codex"
description: "Safely synchronize the local .codex Git repository by auditing changes, committing approved skill/config files, fetching, rebasing, and pushing with sensitive-file and conflict gates."
---

# Update Codex repository

Use this skill when the user asks to update, submit, fetch, rebase, or push the local `.codex` repository.

## Repository

Default repository:

```text
C:\Users\<user>\.codex
```

Resolve the actual path from `CODEX_HOME`, then `$HOME\.codex`.

## Required workflow

1. Inspect repository status, current branch, upstream, remotes, and recent commits.
2. Classify changes before staging:
   - normally committable: `skills/`, `rules/`, tracked documentation, and deliberate configuration source;
   - never commit by default: `auth.json`, session data, locks, logs, caches, snapshots, `.sandbox_migration`, and generated runtime files.
3. If sensitive or ambiguous files are present, stop and report them. Do not stage them.
4. Stage only the approved paths and use a concise Chinese commit message.
5. Run the relevant skill validators and language parsers before committing changed skills.
6. Commit, then fetch with pruning.
7. Rebase the current branch onto its configured upstream. Stop on conflicts; do not auto-resolve semantic conflicts.
8. Verify the rebased history and worktree.
9. Push the current branch to its upstream. If upstream is missing or differs from the intended remote, stop and ask.
10. Report commit id, branch, upstream, pushed range, excluded files, and final status.

## Safety gates

- Never expose or print secret values from `auth.json` or environment variables.
- Never use `git add .` or `git commit -a`.
- Never force-push unless the user explicitly requests it.
- Do not delete or rewrite session databases, locks, or runtime artifacts.
- If rebase or push fails, preserve the repository state and report the exact blocking command and next safe action.

## Completion criteria

Report success only when fetch, rebase, and push all complete and `git status --short` is clean except for explicitly excluded local files.
