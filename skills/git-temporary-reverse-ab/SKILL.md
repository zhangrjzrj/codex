---
name: "git-temporary-reverse-ab"
description: "Temporarily reverse one or more Git commits into the working-tree changes area for A/B testing without changing commit history or the staged index, then restore the exact pre-test workspace state. Use when the user asks to reverse recent or specified commits temporarily, test an older behavior, and later return to HEAD."
---

# Git Temporary Reverse A/B

Use this workflow only after the user authorizes the temporary working-tree mutation.

## Invariants

- Do not create commits, move HEAD, rewrite history, stash, reset, switch branches, or modify the staged index.
- Preserve pre-existing tracked changes and untracked files exactly.
- Resolve and report the target commit hashes before applying anything. Interpret “最近 N 次” from the current `HEAD` first-parent history unless the user specifies otherwise.
- Stop before mutation if a target commit overlaps a pre-existing tracked change, contains a submodule change, or cannot be reversed cleanly.
- Treat binary files as ordinary targets only when they do not overlap existing changes and the reverse patch passes its check.

## Reverse

1. Record `HEAD`, `git status --porcelain=v2`, staged diff names, unstaged diff names, and untracked names.
2. Resolve commits and list their affected paths.
3. Detect overlap between affected paths and pre-existing tracked changes.
4. Generate binary-capable patch files in a validated temporary directory with `git format-patch -1 --binary --full-index --output-directory <dir> <commit>`.
   On Windows, do not pipe `git show` into `git apply`; PowerShell can normalize patch line endings and create whole-file diff noise.
5. Run `git apply --check --reverse` for every patch in newest-to-oldest order against the evolving working tree. Use an isolated temporary worktree for a full dry run when multiple patches overlap each other.
6. Apply with plain `git apply --reverse`; never use `--index`, `--cached`, or `--3way`.
7. Verify staged state is byte-for-byte unchanged and report the resulting changes separately from the preserved baseline.

## Restore

Apply the same saved patches forward in oldest-to-newest order using `git apply --check` followed by plain `git apply`. Verify `HEAD`, staged state, tracked changes, and untracked files match the recorded baseline exactly.

If a test session ends before restoration, report the unresolved reverse state and the exact commit order required to restore it. Never silently discard experimental changes.
