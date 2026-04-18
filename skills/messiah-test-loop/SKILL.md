---
name: messiah-test-loop
description: "Run end-to-end Messiah automated test loops on Windows: optional IncrediBuild compile, launch client, auto-login, execute scenario steps (AOV record or NBS playback), collect logs/dumps/result.json, and gate fixes with approval. Use this for orchestration; use the Telnet and RenderDoc skills for lightweight direct control or offline analysis."
---

# Messiah Test Loop

## Overview

Use this skill to run a reproducible Messiah test loop from Codex with one command. The loop keeps build/launch/login/result handling fixed while scenario behavior stays pluggable.
Most default paths are now inferred from `--repo-root` (supports running from different roots like `E:\messiah_h74` or `F:\messiah_h74`).

This skill is the orchestration layer.
- For direct client control over Telnet, use `messiah-telnet-control`.
- For standalone `.rdc` analysis, use `messiah-renderdoc-analyzer`.

## Workflow

1. Confirm scenario and rounds.
- Built-in scenarios: `aov_record`, `nbs_playback`.
- Run one scenario per loop.

2. Compile (optional).
- Use `messiah-ib-build-fix/scripts/invoke_ib_build.ps1`.
- Stop early on build failure and output machine-readable result.

3. Launch and connect control channel.
- Launch bat is locked to `E:\messiah_h74\cooked_client\Client\Messiah_Demo_常规启动_RenderDoc抓帧专用.bat`.
- Connect Telnet (default 9113; fallback by parsing latest ClientLog).
- Load operator scripts:
  - project `h74_game_operator.py`
  - skill `scripts/in_game/auto_loop_operator.py`

4. Login and execute scenario (optional, controlled by stop point).
- Default login mode is UI-driven (no hardcoded server/account):
  - wait for `UILogin/UILoginMain`
  - optional `--account` only sets account text
  - click start with retry and blocker dismissal
  - fallback to `_auto_loop_operator.fallback_do_gm_login()`
  - auto dismiss `UITraceNotice` at login/scenario gates to avoid blocking tests
- if `UITraceNotice` appears, default behavior is to dismiss and keep going (`--abort-on-trace-notice false`)
- if game process exits (manual close or crash), the loop ends early (`--abort-on-process-exit true`)
- If `--server-profile` is provided, switch to profile login via `_auto_loop_operator.login_with_profile(...)`.
- `--server-profile` mode requires explicit `--account` (no random account fallback).
- Poll `_auto_loop_operator.check_login_ready()` until ready/timeout.
- Start scenario and poll until success/fail/timeout.
- For `nbs_playback`, optional RenderDoc capture on playback start:
  - set `--capture-on-playback-start true`
  - operator runs `startPre()` then either:
    - wait for `montIsPlaying` and delay N frames before no-UI capture (default delay mode)
    - or capture around a specific playback frame using target window mode (`--capture-target-frame`, `--capture-target-mode target_window`)
  - default delay is `--capture-delay-frames 20`
  - target-window defaults: `--capture-window-size 5 --capture-pre-roll 2`
- Default stop point is `after_click_start` (click start game then return immediately).
- Default is not to auto-exit the client after a run (`--request-exit-on-finish false`).
- Two dialogue-driven modes:
  - Manual mode: no auto capture, no auto exit (default).
  - Closed-loop mode: enable capture if asked, and allow auto-exit when running unattended.
- Use `after_operator_load`, `after_login`, or `after_scenario` for deeper automation.

5. Collect artifacts and emit result.
- Save run outputs under `artifacts/test_runs/<run_id>/`.
- Always write `result.json`, `commands.trace`, copied logs, and dumps when present.
- On failure/crash, write `fix_plan.md` and stop for approval before code edits.

6. Optional RenderDoc `.rdc` analysis.
- Enable with `--analyze-rdc true --analyze-rdc-path <capture.rdc>`.
- Analyzer script: `scripts/renderdoc_analyze.py`.
- Writes `rdc_analysis.json` and shader disassembly text into the run directory.
- `result.json` adds `rdc_analysis` summary (`success/partial/failed/skipped`).
- CBuffer value extraction controls:
  - `--analyze-rdc-cb-value-mode layered|strict|aggressive` (default `layered`)
  - `--analyze-rdc-cb-top-n 20` (default 20 variables per block)
  - `--analyze-rdc-cb-neighbor-window 3` (default neighbor probe window)
  - `--analyze-rdc-cb-nonzero-only false` (default exports zero/non-zero values)
  - `--analyze-rdc-target-event-id <eventId>` (optional exact-event lock)

## Commands

Run from any path:
```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\zhangruojun\.codex\skills\messiah-test-loop\scripts\run_loop.ps1 -Scenario aov_record -MaxRounds 1
```

Default behavior: `--reuse-running-client false` (fresh launch by default), `--timeout-login-ui 10`,
and click retry `--click-max-attempts 5 --click-interval-sec 0.5`.

Direct Python entry:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-test-loop\scripts\run_loop.py --scenario nbs_playback --max-rounds 1 --do-build true --require-approval true --stop-point after_scenario
```

Playback + capture on playback start:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-test-loop\scripts\run_loop.py --scenario nbs_playback --max-rounds 1 --do-build false --require-approval false --stop-point after_scenario --capture-on-playback-start true
```

Playback + capture on playback start with custom delay frames:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-test-loop\scripts\run_loop.py --scenario nbs_playback --max-rounds 1 --do-build false --require-approval false --stop-point after_scenario --capture-on-playback-start true --capture-delay-frames 20
```

Playback + capture on target frame:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-test-loop\scripts\run_loop.py --scenario nbs_playback --max-rounds 1 --do-build false --require-approval false --stop-point after_scenario --capture-on-playback-start true --capture-target-frame 120 --capture-target-mode target_window --capture-window-size 5 --capture-pre-roll 2 --capture-frame-mode nbs
```

Playback + post-run RDC analysis:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-test-loop\scripts\run_loop.py --scenario nbs_playback --max-rounds 1 --do-build false --require-approval false --stop-point after_scenario --analyze-rdc true --analyze-rdc-path "F:\h74\水尝试去掉折射\条纹消失去掉散射.rdc" --analyze-rdc-pass-keyword WaterPass --analyze-rdc-stage pixel --analyze-rdc-cb-value-mode layered --analyze-rdc-cb-top-n 20 --analyze-rdc-cb-neighbor-window 3 --analyze-rdc-cb-nonzero-only false
```

Standalone RDC analysis:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-test-loop\scripts\renderdoc_analyze.py --rdc-path "F:\h74\水尝试去掉折射\条纹消失去掉散射.rdc" --pass-keyword WaterPass --stage pixel
```

Fast-fail Telnet smoke (5-second checks):
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-test-loop\scripts\telnet_smoke.py --connect-timeout-sec 5 --io-timeout-sec 5
```

If the user only wants direct control or replay on a running client, prefer:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-telnet-control\scripts\telnet_nbs_playback.py --demo-path "F:\messiah_h74\Messiah\NBSDemo_820.py"
```

If the user only wants `.rdc` analysis, prefer:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-renderdoc-analyzer\scripts\renderdoc_analyze.py --rdc-path "F:\capture.rdc" --pass-keyword WaterPass --stage pixel
```

## Scenario Extension

For adding scenarios, read `references/scenarios.md`.
Only change scenario-specific logic in `scripts/in_game/auto_loop_operator.py` and routing in `scripts/run_loop.py`.

## Guardrails

- Do not modify project code during pure test runs.
- If `result.outcome != pass`, produce analysis first and wait for user approval before patching.
- Keep each run isolated in its own artifact directory.

## Resources

- `scripts/run_loop.ps1`: PowerShell wrapper.
- `scripts/run_loop.py`: Orchestrator.
- `scripts/telnet_driver.py`: Telnet transport and log-based port fallback.
- `scripts/telnet_smoke.py`: 5-second fast-fail Telnet checker.
- `scripts/renderdoc_analyze.py`: offline RenderDoc `.rdc` analyzer.
- `scripts/collect_artifacts.py`: log/dump collector.
- `scripts/in_game/auto_loop_operator.py`: in-game operator loaded through Telnet.
- `references/scenarios.md`: scenario contract and extension notes.
