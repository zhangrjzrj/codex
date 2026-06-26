---
name: messiah-renderdoc-capture
description: "Launch Messiah, log in, play an NBS demo, and automatically trigger RenderDoc capture at playback start or around a target frame. Use when the user wants a live automatic RenderDoc capture rather than offline .rdc analysis."
---

# Messiah RenderDoc Capture

## When to use

Use this skill when the user wants Codex to automatically grab a RenderDoc capture during Messiah playback.

Typical asks:
- auto capture one RenderDoc frame during NBS playback
- play a demo and grab a RenderDoc frame after playback starts
- capture around a specific NBS frame
- launch, login, play, and capture without manually driving the client

If the user already has an `.rdc` file and only wants analysis, use `messiah-renderdoc-analyzer`.
If the user wants a broader launch/login/test loop without focusing on RenderDoc capture, use `messiah-test-loop`.

## Resources

- `scripts/run_renderdoc_capture.py`: thin capture-focused wrapper over `messiah-test-loop/scripts/run_loop.py`

## Workflow

1. Prefer the in-game RenderDoc plugin path for Messiah/H74 workspaces.
- This is the standard path confirmed across `messiah_h74`, `messiah_h74_dx`, and `messiah_official` worktrees.
- Do not default to `qrenderdoc` UI automation, `renderdoccmd capture`, or F12/PrintScreen hotkeys for live capture.
- The successful path is: launch the game with the RenderDoc plugin loaded, run the scenario through Telnet, then call:
```python
import MRenderDoc
MRenderDoc.CaptureWithoutOpen()
```
- Success log markers:
  - `RenderDoc Loaded Success: 10500`
  - `RenderDoc TriggerCapture.`
- Failure marker:
  - `RenderDoc Not Available`

2. Use the RenderDoc capture launcher settings when starting a local Messiah desktop client.
- Known capture-specific batch files:
  - `F:\messiah_h74\cooked_client\Client\Messiah_Demo_常规启动_RenderDoc抓帧专用.bat`
  - `F:\messiah_h74_dx\cooked_client\Client\Messiah_Demo_常规启动_RenderDoc抓帧专用.bat`
  - `F:\messiah_official\cooked_client\Client\Messiah_Demo_常规启动_RenderDoc抓帧专用.bat`
- These batch files enable the `RenderDoc` plugin via `mod_engine_plugins.py RenderDoc True`.
- The important launch flags are:
```text
--shader-log-level=6 --dx12 --disable-streamline --disable-aftermath --console --start=Python --use-pso-precache=1 --ignore-shader-error=1 --force-debug-shader=true --python-args=innerdesktop;
```
- `--dx12`, `--disable-streamline`, and `--disable-aftermath` are important. A `--dx11` external injection path can show `RenderDoc has been detected` while the in-game API still reports `RenderDoc Not Available`.

3. Confirm the playback source.
- Required: `--demo-path`

4. Pick capture mode.
- Default: capture after playback starts with delayed frames
- Optional: target-frame capture with `--target-frame`

5. Run the wrapper.
- The wrapper internally calls `messiah-test-loop/scripts/run_loop.py`
- It forces `scenario=nbs_playback` and `capture-on-playback-start=true`

6. Read the summary first.
- Focus on:
  - `outcome`
  - `renderdoc_capture_mode`
  - `renderdoc_capture_trigger_frame`
  - `renderdoc_capture_triggered_at_frame`
  - `renderdoc_capture_error`
  - guessed `rdc_candidates`

7. Analyze only if needed.
- Default is no analysis
- If the user wants offline analysis afterwards, feed the `.rdc` into `messiah-renderdoc-analyzer`

## Commands

Default delayed capture:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-renderdoc-capture\scripts\run_renderdoc_capture.py --repo-root "F:\messiah_h74" --demo-path "F:\messiah_h74\Messiah\NBSDemo_840.py"
```

Delayed capture with custom delay:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-renderdoc-capture\scripts\run_renderdoc_capture.py --repo-root "F:\messiah_h74" --demo-path "F:\messiah_h74\Messiah\NBSDemo_840.py" --delay-frames 30
```

Target-frame capture:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-renderdoc-capture\scripts\run_renderdoc_capture.py --repo-root "F:\messiah_h74" --demo-path "F:\messiah_h74\Messiah\NBSDemo_840.py" --target-frame 120 --target-mode target_window --frame-mode nbs --window-size 5 --pre-roll 2
```

Capture and then analyze a known `.rdc` path:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-renderdoc-capture\scripts\run_renderdoc_capture.py --repo-root "F:\messiah_h74" --demo-path "F:\messiah_h74\Messiah\NBSDemo_840.py" --analyze-rdc true --analyze-rdc-path "F:\capture.rdc"
```

## Guardrails

- This skill is capture-first, not analysis-first.
- Prefer Messiah's in-game `MRenderDoc.CaptureWithoutOpen()` trigger. Only fall back to external RenderDoc injection/UI automation after proving the in-game plugin path is unavailable.
- Do not reimplement RenderDoc trigger logic when the wrapper can handle it; reuse `messiah-test-loop`.
- Default to delayed playback capture unless the user explicitly gives a target frame.
- Report clearly when capture trigger succeeded but `.rdc` path could not be inferred.
- If logs contain `RenderDoc has been detected` but not `RenderDoc Loaded Success`, treat that as external detection only, not proof that the in-game capture API is usable.
