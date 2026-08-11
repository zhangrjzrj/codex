# CLI Inbox Model

State is unread-only.

```text
inbox.txt
```

Each line is a UTF-8 JSON object with:

- `id`
- `title`
- `cli_title`
- `session_id`
- `workdir`
- `created_at`
- `message`

Supported actions:

- `add` appends one unread line.
- `list` prints all unread lines.
- `show` prints one unread line.
- `ack` deletes one unread line.
- `pick` opens one unread item and then deletes it.

No archive is kept.
