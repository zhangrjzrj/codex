---
name: recover-memory
description: Restore prior progress context from .codex-memory/worklog.md and append an end-of-round memory entry.
---

# recover-memory

Use this skill when the user asks to "恢复记忆", "继续上次进度", or requests context restoration for a specific topic.

## Purpose
- Restore working context from saved progress notes.
- Ensure each round ends with a fresh memory update.

## Source of truth
- Memory log file: `<project-root>\.codex-memory\worklog.md`

## Workflow
1. Identify topic keywords from user request.
2. Resolve project root as current working directory.
3. Ensure `<project-root>\.codex-memory\worklog.md` exists (create directory/file if missing).
4. Open `worklog.md` and find latest entries matching the topic.
5. Return a concise restore summary:
   - Last known status
   - Key conclusions
   - Pending tasks / next action
6. Continue execution based on restored context.

## End-of-round writeback (mandatory)
At the end of each conversation round, append one entry to `<project-root>\.codex-memory\worklog.md` using this template:

```md
## YYYY-MM-DD HH:mm - <topic>
- Progress: ...
- Key conclusions: ...
- Next step: ...
```

Rules:
- Keep entries short (3-6 bullets max).
- Prefer concrete file paths, ports, instance ids, and versions.
- If nothing changed, still write a "No material change" entry.
