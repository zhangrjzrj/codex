---
name: cli-inbox
description: File-backed unread inbox for CLI task notifications. Use when Codex needs a persistent list of unread completions, a text-file carrier for notifications, or a minimal open/ack workflow where read items are removed and only unread items remain.
---

# CLI Inbox

Use this skill to manage a small unread-only inbox in one text file.

## Workflow

1. Add a pending item when a task completes.
2. List pending items at any time.
3. Show one item when you want details.
4. Ack one item after you have read or handled it.

## Rules

- Keep only unread items.
- Do not create an archive.
- Treat ack as deletion of the unread record.
- Prefer stable identifiers over window titles alone.

## Storage

Use the bundled script to store all unread items in one text file.
Each record should include:

- item id
- title
- CLI title
- session id
- workdir
- created time
- message

## Commands

See `scripts/task_inbox.py` for the supported operations:

- `add`
- `list`
- `show`
- `ack`
- `pick`

For default red-dot style提醒, `scripts/watch_title.py` can mirror unread count onto the current CLI window title.

Use `show` to inspect an item first, then `ack` to remove it. Use `pick` when you want a chooser that opens one unread item and acks it.
