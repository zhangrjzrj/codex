---
name: "duomilu-chat-input"
description: "Stably inject Chinese or ASCII task prompts into an active Duomilu chat on an Android emulator/device, using clipboard paste plus Android keyevent 279 before falling back to adb text input. Use when Codex needs to send real Duomilu chat instructions without relying on fragile raw adb Chinese typing, especially during Duomilu/App closed-loop tests, chat-page recovery, or external-task feedback verification."
---

# Duomilu Chat Input

Use this skill to send a prompt into the real Duomilu chat composer and capture evidence that the send path worked.

Prefer this skill over ad hoc `adb shell input text` when the prompt contains Chinese, spaces, punctuation, or when the app may still be on a select page instead of the real chat page.

## Workflow

1. Confirm the target emulator/device id.
2. Run `scripts/send_duomilu_prompt.ps1 -DeviceId <device-id> -Prompt "<text>"`.
3. Read the returned JSON for `used_prompt`, `before_dump`, and `after_dump`.
4. Inspect the emitted UI dumps and optional screenshots under the evidence directory.
5. Continue the closed loop only after the send path is proven.

## What The Script Does

- Verifies ADB availability and that the Duomilu app is foreground.
- Dumps the current UI tree before input.
- Detects whether the current page is already `pages/home/chat*`; if not, it tries to tap into chat first.
- Locates the chat composer near the bottom of the page.
- Clears the current prompt field.
- Attempts clipboard paste plus Android `keyevent 279`.
- Temporarily reuses the host clipboard for paste-first input, and starts an out-of-process restore guard so the clipboard is restored even if the main run is interrupted.
- Falls back to `adb shell input text` only when paste is unavailable.
- Sends by tapping the send button when found, otherwise falls back to Enter.
- Dumps the UI tree again after sending and prints a concise JSON result.

## Success Criteria

- `used_prompt` equals the intended Chinese prompt and does not degrade to an ASCII fallback.
- `host_clipboard_mode` is `guarded_restore` when host clipboard paste was used.
- `after_dump` shows the active chat page.
- The chat screenshot or dump reflects that the new message was sent, or the page enters a visible processing state.

## Failure Handling

- If the script throws because the app is not foreground, first restore the emulator to the target Duomilu page and rerun.
- If `used_prompt` differs from the original prompt, treat that as a degraded path and inspect whether fallback input was used.
- If send succeeds but no task feedback appears, continue the test loop by inspecting frontend chat snapshots, backend logs, or external task state. Do not blame the input path by default.

## Use Notes

- Pass `-DeviceId` explicitly when multiple emulators are online.
- The default evidence directory is relative to the current workspace: `.local-artifacts/runtime-evidence/duomilu-send-prompt/`.
- This skill solves prompt injection reliability. It does not by itself prove that the downstream external task flow succeeded.

## Scripts

- `scripts/send_duomilu_prompt.ps1`
  Send a prompt into the active Duomilu chat using paste-first input and write before/after UI evidence.
