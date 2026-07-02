---
name: "duomilu-chat-input"
description: "Stably inject Chinese or ASCII task prompts into an active Duomilu chat on an Android emulator/device, preferring the frontend debug command path so chat.vue itself performs the real send, with ADB input only as fallback. Use when Codex needs to send real Duomilu chat instructions without relying on fragile raw adb Chinese typing, especially during Duomilu/App closed-loop tests, chat-page recovery, or external-task feedback verification."
---

# Duomilu Chat Input

Use this skill to send a prompt into the real Duomilu chat composer and capture evidence that the send path worked.

Prefer this skill over ad hoc `adb shell input text` when the prompt contains Chinese, spaces, punctuation, or when the app may still be on a select page instead of the real chat page.

## Workflow

1. Resolve the current app space from the working directory: `D:\hanhan\app`, `app1`, `app2`, `app3`, `app4`, or `app5`.
2. Prefer the script in the current space: `<space>\scripts\send_duomilu_prompt.ps1`.
3. Run `scripts/send_duomilu_prompt.ps1 -Prompt "<text>"`; pass `-DeviceId`, `-MemberId`, or `-HttpBase` only when the defaults are wrong.
4. Read the returned JSON for `space`, `device_id`, `http_base`, `member_id`, `submit_mode`, `command_report`, `before_dump`, and `after_dump`.
5. Inspect the emitted UI dumps and optional screenshots under the evidence directory.
6. Continue the closed loop only after the send path is proven.

## Space Defaults

The script should infer defaults from the current working directory and `config/localDebug.js`.

| Space | Default device | Default backend |
| --- | --- | --- |
| `D:\hanhan\app1` | `emulator-5554` | `config/localDebug.js` or `http://192.168.200.128:8784` |
| `D:\hanhan\app2` | `emulator-5556` | `config/localDebug.js` or `http://192.168.200.128:8785` |
| `D:\hanhan\app3` | `emulator-5558` | `config/localDebug.js` or `http://192.168.200.128:8786` |
| `D:\hanhan\app4` | `emulator-5560` | `config/localDebug.js` or `http://192.168.200.128:8787` |
| `D:\hanhan\app5` | `emulator-5560` | `config/localDebug.js` or `http://192.168.200.128:8788` |
| `D:\hanhan\app` | no hard assumption | read `config/localDebug.js`; pass `-DeviceId` if ambiguous |

Do not assume app4. If the current task says app1, use app1's workspace, backend, account, and emulator.

## What The Script Does

- Verifies ADB availability and that the Duomilu app is foreground.
- Dumps the current UI tree before send.
- Posts a debug `send_text` command to `/webapi/debug/chat-command`, so the frontend chat page itself calls its real `send(text)` logic.
- Waits for the frontend debug bridge to report command consumption.
- Uses ADB text injection only when the explicit `-AllowAdbFallback` switch is passed and the debug command path fails.
- Dumps the UI tree again after sending and prints a concise JSON result.

## Success Criteria

- `used_prompt` equals the intended Chinese prompt and does not degrade to an ASCII fallback.
- `submit_mode` is `frontend_debug_command` in the normal path.
- `command_report` is present and indicates the frontend accepted the command.
- `after_dump` shows the active chat page.
- The chat screenshot or dump reflects that the new message was sent, or the page enters a visible processing state.

## Failure Handling

- If the script throws because the app is not foreground, first restore the emulator to the target Duomilu page and rerun.
- If `used_prompt` differs from the original prompt, treat that as a degraded path and inspect whether fallback input was used.
- If send succeeds but no task feedback appears, continue the test loop by inspecting frontend chat snapshots, backend logs, or external task state. Do not blame the input path by default.

## Use Notes

- Pass `-DeviceId` explicitly when multiple emulators are online and the inferred device is not the target.
- Pass `-HttpBase` explicitly only when the current workspace is intentionally talking to a nonstandard backend instance.
- The default evidence directory is relative to the current workspace: `.local-artifacts/runtime-evidence/duomilu-send-prompt/`.
- This skill solves prompt injection reliability. It does not by itself prove that the downstream external task flow succeeded.

## Scripts

- `scripts/send_duomilu_prompt.ps1`
  Send a prompt into the active Duomilu chat using paste-first input and write before/after UI evidence.
