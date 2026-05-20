---
name: messiah-telnet-control
description: "Connect to a running Messiah client over Telnet, load in-game operator scripts, send Python commands, set window resolution with MUI.SetWindowPos, start scenarios such as NBS playback, poll status, and save concise traces."
---

# Messiah Telnet Control

## When to use

Use this skill when the user wants to control an already running Messiah client through Telnet, or wants a lightweight path that avoids the full `messiah-test-loop` orchestrator.

Typical asks:
- connect to the client and send one or more Python commands
- set the client window resolution, for example `2580x1080`, by executing `MUI.SetWindowPos(width,height)`
- load `auto_loop_operator.py` and trigger `nbs_playback`
- check Telnet health or discover the bound port from logs
- do a direct replay after the client is already open

If the user wants build + launch + login + scenario + artifacts in one flow, use `messiah-test-loop` instead.

## Resources

- `scripts/telnet_driver.py`: Telnet transport with log-based port fallback
- `scripts/telnet_smoke.py`: fast-fail health check
- `scripts/telnet_exec.py`: connect, optionally load a script, then send one or more commands
- `scripts/telnet_set_window_pos.py`: set client window size with `import MUI;MUI.SetWindowPos(width,height)`
- `scripts/telnet_nbs_playback.py`: direct NBS playback helper for `NBSDemo*.py`

## Workflow

1. Confirm the client is already running.
- Prefer `tasklist` for `Game_x64h.exe` or `Game_x64r.exe`.
- Default log dir is `F:\messiah_h74\Messiah\LocalData\Log`.

2. Confirm Telnet is ready.
- Default port is `9113`.
- If connect fails, use `scripts/telnet_smoke.py` or let `telnet_driver.py` parse the latest `ClientLog`.

3. Load operator script when needed.
- Default operator is `C:\Users\zhangruojun\.codex\skills\messiah-test-loop\scripts\in_game\auto_loop_operator.py`.
- Use `scripts/telnet_exec.py --load-script <path>` to inject it.

4. Send commands.
- For generic control, send exact Python commands with `scripts/telnet_exec.py --command ...`.
- For window resolution changes, prefer `scripts/telnet_set_window_pos.py <width> <height>`.
- Window size uses pixels, for example `2580 1080`; this is separate from NBS aspect ratio such as `21.5:9`.
- For direct playback, use `scripts/telnet_nbs_playback.py`.

5. Poll or verify.
- For scenario state, poll `_auto_loop_operator.poll_scenario()`.
- Treat `status=success` as pass.
- If the socket resets after success, report success first; that usually means the control channel closed after completion.

## Commands

Health check:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-telnet-control\scripts\telnet_smoke.py --connect-timeout-sec 5 --io-timeout-sec 5
```

Send one command:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-telnet-control\scripts\telnet_exec.py --load-script "C:\Users\zhangruojun\.codex\skills\messiah-test-loop\scripts\in_game\auto_loop_operator.py" --command "_auto_loop_operator.check_login_ready()"
```

Direct playback with a demo script:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-telnet-control\scripts\telnet_nbs_playback.py --demo-path "F:\messiah_h74\Messiah\NBSDemo_820.py"
```

Set window resolution:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-telnet-control\scripts\telnet_set_window_pos.py 2580 1080
```

## Guardrails

- Do not silently rebuild or patch project code from this skill.
- Prefer exact commands and short traces.
- If login is not ready, either report that clearly or use the explicit login helper path; do not guess hidden game state.
