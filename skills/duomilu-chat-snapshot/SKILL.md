---
name: "duomilu-chat-snapshot"
description: "Read the latest Duomilu frontend chat content, active task state, and rendered message list from any specified Android emulator/device by consuming chat_render_snapshot debug events. Use when Codex needs precise frontend-visible chat evidence for Duomilu/App4 instead of incomplete screenshots or UI dumps, especially for message duplication, stale waiting cards, task-site mismatch, socket send verification, or any WebView black-box debugging."
---

# Duomilu Chat Snapshot

Use this skill to inspect what the Duomilu frontend actually rendered in the chat page.

Do not rely on screenshots or `uiautomator dump` when WebView content is incomplete. Prefer this skill whenever the question is "what did the frontend really show?"

## Workflow

1. Identify the target emulator/device id, for example `emulator-5560`.
2. When the backend uses instance-specific runtime directories such as `app3` or `app4`, pass `-InstanceId <instance-id>`.
3. Run `scripts/read_duomilu_chat_snapshot.ps1 -DeviceId <device-id> [-InstanceId <instance-id>]`.
4. Read the latest `chat_render_snapshot` payload for that device.
5. Use the returned `visible_messages`, `active_task`, `session_id`, and `route` as the source of truth for frontend-visible content.

## Output Meaning

- `visible_messages`: Last rendered chat messages from the frontend message list.
- `active_task`: Current frontend active external task badge state.
- `route`: Current page route marker reported by the frontend.
- `session_id`: Current frontend chat session id.
- `reason`: Why the snapshot was emitted, for example `messages_changed`.

## Use Notes

- This skill reads backend debug logs produced by the frontend `clientAvDebug` channel.
- This skill is device-aware. Always pass `-DeviceId` explicitly when multiple emulators are online.
- This skill now supports instance-aware log lookup. Prefer `-InstanceId app3` or similar when the backend writes logs under `runtime/instances/<instance-id>/logs/`.
- If no snapshot is found, first confirm the app build includes the `chat_render_snapshot` debug event and that `LOCAL_DEBUG` is enabled.

## Scripts

- `scripts/read_duomilu_chat_snapshot.ps1`
  Read the newest `chat_render_snapshot` event for a specific device and print a concise JSON snapshot.
