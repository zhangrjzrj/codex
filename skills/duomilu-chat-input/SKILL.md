---
name: "duomilu-chat-input"
description: "Stably inject Chinese or ASCII task prompts into an active Duomilu chat on an Android emulator/device, preferring the frontend debug command path so chat.vue itself performs the real send, with ADB input only as fallback. Use when Codex needs to send real Duomilu chat instructions without relying on fragile raw adb Chinese typing, especially during Duomilu/App closed-loop tests, chat-page recovery, or external-task feedback verification."
---

# Duomilu Chat Input

Use this skill to send a prompt into the real Duomilu chat composer and capture evidence that the send path worked.

Prefer this skill over ad hoc `adb shell input text` when the prompt contains Chinese, spaces, punctuation, or when the app may still be on a select page instead of the real chat page.

## Workflow

1. Resolve the target app space from the working directory or pass it explicitly with `-ProjectRoot`, for example `D:\hanhan\app1`.
2. Run the global script: `C:\Users\zhangrjzrj\.codex\skills\duomilu-chat-input\scripts\send_duomilu_prompt.ps1 -Prompt "<text>" -ProjectRoot <space-root>`.
3. Let the script read `<space-root>\config\spaceConfig.json` first; it falls back to `config\localDebug.js` only for older spaces.
4. Pass `-DeviceId`, `-MemberId`, `-SessionId`, or `-HttpBase` only when the inferred defaults are intentionally wrong.
5. Read the returned JSON for `project_root`, `space`, `device_id`, `http_base`, `member_id`, `target_member_id`, `target_session_id`, `submit_mode`, `command_report`, `before_dump`, and `after_dump`.
6. Inspect the emitted UI dumps and optional screenshots under the evidence directory.
7. Continue the closed loop only after the send path is proven.

## Space Defaults

The script should infer defaults from `<space-root>\config\spaceConfig.json` and only fall back to `config/localDebug.js` when the JSON config is absent.

| Space | Default device | Default backend |
| --- | --- | --- |
| `D:\hanhan\app1` | `emulator-5554` | `spaceConfig.json` or `http://192.168.200.128:8784` |
| `D:\hanhan\app2` | `emulator-5556` | `spaceConfig.json` or workspace fallback |
| `D:\hanhan\app3` | `emulator-5558` | `spaceConfig.json` or workspace fallback |
| `D:\hanhan\app4` | `emulator-5560` | `spaceConfig.json` or workspace fallback |
| `D:\hanhan\app5` | `emulator-5562` | `spaceConfig.json` or workspace fallback |
| `D:\hanhan\app` | no hard assumption | read `spaceConfig.json` or fallback config; pass `-DeviceId` if ambiguous |

Do not assume app4. If the current task says app1, use app1's workspace, backend, account, and emulator.

## What The Script Does

- Verifies ADB availability and that the Duomilu app is foreground.
- Dumps the current UI tree before send.
- Resolves the correct member/session pair for the active frontend chat when possible, so debug commands target the real session instead of a stale default.
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
- Current ADB fallback still contains a documented `WORKAROUND` that uses verified chat-page coordinates when the WebView dump omits the composer or send button nodes.
- This skill solves prompt injection reliability. It does not by itself prove that the downstream external task flow succeeded.

## Scripts

- `scripts/send_duomilu_prompt.ps1`
  Send a prompt into the active Duomilu chat using the frontend debug command path first, then documented ADB fallback if needed, and write before/after UI evidence.
