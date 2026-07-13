---
name: "duomilu-chat-input"
description: "Stably inject Chinese or ASCII task prompts into an active Duomilu chat on a specific Android emulator/device through an ADB-directed client deep link, so chat.vue itself performs the real send without backend polling or coordinate input."
---

# Duomilu Chat Input

Use this skill to send a prompt into the real Duomilu chat composer on a specific ADB device and capture evidence that the send path worked.

Prefer this skill over backend debug commands, ad hoc `adb shell input text`, or coordinate tapping. The target identity is the ADB `DeviceId`.

## Workflow

1. Resolve the target app space from the working directory or pass it explicitly with `-ProjectRoot`, for example `D:\hanhan\app1`.
2. Run the global script: `C:\Users\zhangrjzrj\.codex\skills\duomilu-chat-input\scripts\send_duomilu_prompt.ps1 -Prompt "<text>" -ProjectRoot <space-root>`.
3. Let the script read `<space-root>\config\spaces\<space>.json`.
4. Pass `-DeviceId` only when the inferred device is intentionally wrong.
5. Read the returned JSON for `project_root`, `space`, `device_id`, `submit_mode`, `deep_link`, `before_dump`, and `after_dump`.
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

- Verifies ADB availability and that the target Duomilu app is foreground on the selected device.
- Dumps the current UI tree before send.
- Sends `duomilu://debug-chat?action=send_text&text=...&command_id=...` through `adb -s <DeviceId> shell am start`.
- The App receives the deep link on that device, de-duplicates it by `command_id`, and chat.vue submits through the real send path after the chat restore gate opens.
- Dumps the current UI tree after send.
- Dumps the UI tree again after sending and prints a concise JSON result.

## Success Criteria

- `used_prompt` equals the intended Chinese prompt and does not degrade to an ASCII fallback.
- `submit_mode` is `adb_deeplink_client_api`.
- `after_dump` shows the active chat page.
- The chat screenshot or dump reflects that the new message was sent, or the page enters a visible processing state.

## Failure Handling

- If the script throws because the app is not foreground, first restore the emulator to the target Duomilu page and rerun.
- If `used_prompt` differs from the original prompt, treat that as a failure.
- If send succeeds but no task feedback appears, continue the test loop by inspecting frontend chat snapshots, backend logs, or external task state. Do not blame the input path by default.

## Use Notes

- Pass `-DeviceId` explicitly when multiple emulators are online and the inferred device is not the target.
- The default evidence directory is relative to the current workspace: `.local-artifacts/runtime-evidence/duomilu-send-prompt/`.
- This skill solves prompt injection reliability. It does not by itself prove that the downstream external task flow succeeded.

## Scripts

- `scripts/send_duomilu_prompt.ps1`
  Send a prompt into the active Duomilu chat using the ADB-directed client deep link, and write before/after UI evidence.
