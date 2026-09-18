---
name: "recover-memory"
description: "Restore prior progress context from project-local and shared memory stores, then append a workdir-bound recovery entry."
---

# recover-memory

Use this skill when the user asks to "恢复记忆", "继续上次进度", or requests context restoration for a specific topic.

## Purpose
- Restore working context from saved progress notes.
- Ensure each round ends with a fresh memory update.

## Source of truth
- Project-local memory root: `<project-root>\.j-memory\`
- Shared memory root: `<CODEX_HOME>\memories\`
- Never create or write a parallel legacy project-memory directory.
- The active working directory MUST be recorded as `Workdir:` in every entry.

## Workflow
1. Identify topic keywords from user request.
2. Resolve project root as current working directory.
3. Resolve `<project-root>\.j-memory\index.md` and relevant local thread files; create them if missing.
4. Resolve `<CODEX_HOME>\memories\index.md` and the relevant shared project/thread files; create them if missing.
5. Filter shared entries by exact or nearest `Workdir:` before matching topic keywords.
6. Prefer the newest relevant entry when local and shared memories overlap.
7. Return a concise restore summary:
   - Last known status
   - Key conclusions
   - Pending tasks / next action
8. Continue execution based on restored context.

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
- Update the matching `.j-memory/threads/<topic>.md` and `.j-memory/index.md` in the same round.
- Keep entries short (3-6 bullets max).
- Prefer concrete file paths, ports, instance ids, and versions.
- If nothing changed, still write a "No material change" entry.
