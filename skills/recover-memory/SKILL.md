---
name: recover-memory
description: Restore prior progress context from the shared Codex memory store and append a workdir-bound memory entry.
---

# recover-memory

Use this skill when the user asks to "恢复记忆", "继续上次进度", or requests context restoration for a specific topic.

## Purpose
- Restore working context from saved progress notes.
- Ensure each round ends with a fresh memory update.

## Source of truth
- Shared memory root: `<CODEX_HOME>\memories\`
- The active working directory MUST be recorded as `Workdir:` in every entry.

## Workflow
1. Identify topic keywords from user request.
2. Resolve project root as current working directory.
3. Resolve `<CODEX_HOME>\memories\index.md` and the relevant project/thread files; create them if missing.
4. Filter by exact or nearest `Workdir:` before matching topic keywords.
5. Return a concise restore summary:
   - Last known status
   - Key conclusions
   - Pending tasks / next action
6. Continue execution based on restored context.

## End-of-round writeback (mandatory)
At the end of each conversation round, append one entry to `<CODEX_HOME>\memories\worklog.md` using this template:

```md
## YYYY-MM-DD HH:mm - <topic>
- Workdir: <absolute working directory>
- Progress: ...
- Key conclusions: ...
- Next step: ...
```

Rules:
- Keep entries short (3-6 bullets max).
- Prefer concrete file paths, ports, instance ids, and versions.
- If nothing changed, still write a "No material change" entry.
