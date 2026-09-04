---
name: project-memory-manager
description: "Persist concise workdir-bound memory in the shared Codex memory store and restore relevant topic memory on demand."
---

# Project Memory Manager

## When to use

Use this skill when:

- a conversation round is ending and current progress should be saved
- the user says “恢复记忆”
- the user says “查看一下关于 xxx 问题的文档，并恢复记忆”
- the user asks to resume prior context in the current project
- the user explicitly declares the current window topic

## Goal

Keep shared memory low-coupled and resumable across projects and worktrees.

Use this structure:

```text
<CODEX_HOME>/memories/
  index.md
  projects/<project-key>.md
  threads/
    <topic>.md
```

Memory restore/search must always start from this fixed shared path:

- `<CODEX_HOME>\memories\index.md`
- `<CODEX_HOME>\memories\projects\*.md`
- `<CODEX_HOME>\memories\threads\*.md`

Every topic and entry MUST include:

```md
Workdir: <absolute working directory>
```

## Structure rules

### `index.md`

Use it as a lightweight topic index.
Each topic should include:

- topic name
- short summary
- latest update time
- thread file path

### `threads/*.md`

Store detailed memory per stable topic.
Do not put all unrelated conversations into one shared file.

Topic naming should prefer:

```text
YYYYMMDD-stable-topic-name.md
```

The current stable topic name should follow this priority:

1. `/rename` new name for the current window/thread
2. user-declared current topic
3. Codex inferred topic from the current window main line

If `/rename` is available in the host, treat it as the default source of truth for the window topic and bind memory topic name to it automatically.

Prefer stable topic names such as:

- `20260401-minigif-crash.md`
- `20260401-tracy-stutter-analysis.md`
- `20260401-nbs-playback-840.md`

## Write rule

At the end of each round:

1. Decide the current stable topic
2. Append concise notes into the matching `threads/*.md`
3. Update `index.md`

If the user explicitly declared the topic for the current window, prefer that topic even if the window temporarily includes several side topics.
Every `/rename` must immediately synchronize the current memory topic in the same round, without requiring an extra "set current topic" command.

If a rename is needed after the user declares a new topic or uses `/rename`:

1. rename only the thread file bound to the current window
2. update only the matching entry in `index.md`
3. continue future writes in the renamed file

Do not rename unrelated thread files.
Do not rewrite unrelated index entries.

Recommended thread entry format:

```md
## YYYY-MM-DD HH:mm:ss
- 当前目标：
- 已完成：
- 关键结论：
- 关键路径：
- 下一步：
```

## Restore rule

When the user asks to restore memory:

1. Read `<CODEX_HOME>\memories\index.md`
2. Filter index entries by the current absolute working directory
3. Locate the most relevant topic file in `<CODEX_HOME>\memories\threads\`
4. Read the recent relevant entries from that topic file
5. Summarize the conclusions first
6. Continue execution

Do not dump the whole index or whole thread unless the user explicitly asks.

## Guardrails

- This is shared memory; workdir binding prevents cross-project mixing
- Never write a memory entry without an absolute `Workdir:`
- Even inside one project directory, avoid mixing unrelated topics into one single long file
- A `/rename` or user-declared topic rename applies only to the current window/topic binding
- Never let one window's topic rename affect other windows' memory files
- If the shared memory directories do not exist, create them
- Keep entries short, factual, and resumable

## Suggested trigger sentences

- 恢复记忆
- 恢复一下之前关于 xxx 的记忆
- 查看一下关于 xxx 问题的文档，并恢复记忆
- 把当前进度记下来
- 当前主题是 xxx
- 把这个窗口主题设为 xxx
- 记住这个窗口的主题叫 xxx
- /rename xxx


